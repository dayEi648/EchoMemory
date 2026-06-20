"""用户画像服务测试。"""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.ai import langchain as ai_langchain
from echomemory_backend.ai.clients import deepseek as deepseek_module
from echomemory_backend.ai.clients.deepseek import ChatResponse
from echomemory_backend.ai.graphs import checkpointer as ai_checkpointer
from echomemory_backend.ai.graphs.conversation.builder import build_graph
from echomemory_backend.models.ai_conversation import AIConversation
from echomemory_backend.models.user import User
from echomemory_backend.models.user_profile import UserProfile
from echomemory_backend.services import (
    ai_conversation_service,
    user_profile_service,
)
from echomemory_backend.services import user_profile_service as user_profile_module


def _register_and_login(client, username: str) -> str:
    """注册并登录测试用户，返回 access token。"""
    from tests.api_helpers import api_data

    register_resp = client.post(
        "/api/v1/auth/register",
        data={"username": username, "password": "secret123", "nickname": username},
    )
    assert register_resp.status_code == 201
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert resp.status_code == 200
    return api_data(resp)["access_token"]


async def _create_user(db_session: AsyncSession, username: str) -> User:
    """在数据库中直接创建测试用户。"""
    user = User(
        username=username,
        password_hash="hashed-secret",
        nickname=username,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _create_conversation(
    db_session: AsyncSession, user: User
) -> AIConversation:
    """创建空 AI 会话。"""
    conversation, _ = await ai_conversation_service.create_conversation(
        db_session, user_id=user.id
    )
    return conversation


async def _seed_conversation_messages(
    conversation: AIConversation,
    human_messages: list[str],
    ai_messages: list[str],
) -> None:
    """向指定会话的 checkpoint 中写入测试消息。

    human_messages 与 ai_messages 按顺序交替写入，human 消息数量必须等于
    传入列表长度。用于直接测试用户画像更新逻辑，不经过真实 LLM。
    """
    graph = build_graph(conversation.model)
    config = {
        "configurable": {"thread_id": conversation.thread_id},
        "recursion_limit": 15,
    }

    messages: list[HumanMessage | AIMessage] = []
    max_len = max(len(human_messages), len(ai_messages))
    for index in range(max_len):
        if index < len(human_messages):
            messages.append(HumanMessage(content=human_messages[index]))
        if index < len(ai_messages):
            messages.append(AIMessage(content=ai_messages[index]))

    await graph.aupdate_state(config, {"messages": messages})


class _FakeDeepSeekClientFactory:
    """构造可控制返回内容的 Fake DeepSeekClient。"""

    def __init__(self, responses: list[ChatResponse] | None = None):
        self.responses = responses or []
        self.call_count = 0

    def build(self):
        responses = self.responses
        factory = self

        class _FakeDeepSeekClient:
            def __init__(self, model, **kwargs):
                self.model = model
                self._enable_thinking = kwargs.get("enable_thinking", False)

            async def chat(self, messages, **kwargs):
                index = factory.call_count
                factory.call_count += 1
                if index < len(responses):
                    return responses[index]
                return ChatResponse(content="", model=self.model)

            async def chat_stream(self, messages, **kwargs):
                # chat_stream 用于 AI 对话生成，不消耗 responses 列表，
                # 避免与 judge/update 的 chat 调用共享索引。
                if self._enable_thinking:
                    yield ChatResponse(
                        content="",
                        reasoning_content="思考中",
                        model=self.model,
                    )
                yield ChatResponse(content="reply", model=self.model)

            def chat_sync(self, messages, **kwargs):
                index = factory.call_count
                factory.call_count += 1
                if index < len(responses):
                    return responses[index]
                return ChatResponse(content="", model=self.model)

            def chat_stream_sync(self, messages, **kwargs):
                if self._enable_thinking:
                    yield ChatResponse(
                        content="",
                        reasoning_content="思考中",
                        model=self.model,
                    )
                yield ChatResponse(content="reply", model=self.model)

        return _FakeDeepSeekClient


def _patch_deepseek_client(monkeypatch, responses: list[ChatResponse]):
    """用指定响应序列替换 DeepSeekClient。

    同时覆盖 langchain 适配器、原始客户端模块以及用户画像服务模块中的
    DeepSeekClient 引用，确保所有调用路径都使用同一个 Fake 客户端。
    """
    factory = _FakeDeepSeekClientFactory(responses)
    fake_cls = factory.build()
    monkeypatch.setattr(ai_langchain.deepseek_chat, "DeepSeekClient", fake_cls)
    monkeypatch.setattr(deepseek_module, "DeepSeekClient", fake_cls)
    monkeypatch.setattr(user_profile_module, "DeepSeekClient", fake_cls)
    return factory


@pytest.mark.asyncio
async def test_no_update_when_human_count_not_multiple_of_four(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    fake_deepseek_client,
):
    """human 消息数量不是 4 的倍数时，不应触发画像更新。"""
    user = await _create_user(db_session, "profile_user_1")
    conversation = await _create_conversation(db_session, user)
    await _seed_conversation_messages(
        conversation,
        human_messages=["msg1", "msg2", "msg3"],
        ai_messages=["reply1", "reply2", "reply3"],
    )

    await user_profile_service.maybe_update_user_profile(
        db_session, user_id=user.id, conversation=conversation
    )

    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_profile_created_when_judge_returns_true(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    monkeypatch,
):
    """判断为 true 时，应创建并保存用户画像。"""
    factory = _patch_deepseek_client(
        monkeypatch,
        [
            ChatResponse(content="true", model="deepseek-v4-flash"),
            ChatResponse(content="喜欢流行音乐，常用中文交流。", model="deepseek-v4-flash"),
        ],
    )

    user = await _create_user(db_session, "profile_user_2")
    conversation = await _create_conversation(db_session, user)
    await _seed_conversation_messages(
        conversation,
        human_messages=["msg1", "msg2", "msg3", "msg4"],
        ai_messages=["reply1", "reply2", "reply3", "reply4"],
    )

    await user_profile_service.maybe_update_user_profile(
        db_session, user_id=user.id, conversation=conversation
    )

    assert factory.call_count == 2
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    assert profile is not None
    assert "喜欢流行音乐" in profile.content


@pytest.mark.asyncio
async def test_judge_false_skips_update(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    monkeypatch,
):
    """判断为 false 时，不应创建画像。"""
    factory = _patch_deepseek_client(
        monkeypatch,
        [ChatResponse(content="false", model="deepseek-v4-flash")],
    )

    user = await _create_user(db_session, "profile_user_3")
    conversation = await _create_conversation(db_session, user)
    await _seed_conversation_messages(
        conversation,
        human_messages=["msg1", "msg2", "msg3", "msg4"],
        ai_messages=["reply1", "reply2", "reply3", "reply4"],
    )

    await user_profile_service.maybe_update_user_profile(
        db_session, user_id=user.id, conversation=conversation
    )

    assert factory.call_count == 1
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_judge_retries_on_invalid_response_then_true(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    monkeypatch,
):
    """非法响应时应重试，最终 true 仍应更新画像。"""
    factory = _patch_deepseek_client(
        monkeypatch,
        [
            ChatResponse(content="maybe", model="deepseek-v4-flash"),
            ChatResponse(content="true", model="deepseek-v4-flash"),
            ChatResponse(content="喜欢摇滚音乐。", model="deepseek-v4-flash"),
        ],
    )

    user = await _create_user(db_session, "profile_user_4")
    conversation = await _create_conversation(db_session, user)
    await _seed_conversation_messages(
        conversation,
        human_messages=["msg1", "msg2", "msg3", "msg4"],
        ai_messages=["reply1", "reply2", "reply3", "reply4"],
    )

    await user_profile_service.maybe_update_user_profile(
        db_session, user_id=user.id, conversation=conversation
    )

    assert factory.call_count == 3
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    assert profile is not None
    assert "喜欢摇滚音乐" in profile.content


@pytest.mark.asyncio
async def test_judge_exceeds_retries_gives_up(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    monkeypatch,
):
    """超过最大重试次数仍非法时，应放弃本次更新。"""
    factory = _patch_deepseek_client(
        monkeypatch,
        [
            ChatResponse(content="invalid", model="deepseek-v4-flash"),
            ChatResponse(content="invalid", model="deepseek-v4-flash"),
            ChatResponse(content="invalid", model="deepseek-v4-flash"),
        ],
    )

    user = await _create_user(db_session, "profile_user_5")
    conversation = await _create_conversation(db_session, user)
    await _seed_conversation_messages(
        conversation,
        human_messages=["msg1", "msg2", "msg3", "msg4"],
        ai_messages=["reply1", "reply2", "reply3", "reply4"],
    )

    await user_profile_service.maybe_update_user_profile(
        db_session, user_id=user.id, conversation=conversation
    )

    assert factory.call_count == 3
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_profile_update_serializes_per_user(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    monkeypatch,
):
    """同一用户的画像更新应串行排队执行。"""
    active_count = 0
    max_active = 0

    class _TrackingFakeClient:
        def __init__(self, model, **kwargs):
            self.model = model
            self._enable_thinking = kwargs.get("enable_thinking", False)

        async def chat(self, messages, **kwargs):
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            # 模拟一定的处理时间，让并发更容易暴露问题
            await asyncio.sleep(0.01)
            active_count -= 1
            content = "true" if "判断" in messages[0].content else "汇总结果"
            return ChatResponse(content=content, model=self.model)

        async def chat_stream(self, messages, **kwargs):
            yield ChatResponse(content="", model=self.model)

        def chat_sync(self, messages, **kwargs):
            return ChatResponse(content="", model=self.model)

        def chat_stream_sync(self, messages, **kwargs):
            yield ChatResponse(content="", model=self.model)

    monkeypatch.setattr(
        ai_langchain.deepseek_chat, "DeepSeekClient", _TrackingFakeClient
    )
    monkeypatch.setattr(deepseek_module, "DeepSeekClient", _TrackingFakeClient)
    monkeypatch.setattr(user_profile_module, "DeepSeekClient", _TrackingFakeClient)

    user = await _create_user(db_session, "profile_user_6")
    conversation1 = await _create_conversation(db_session, user)
    conversation2 = await _create_conversation(db_session, user)

    await _seed_conversation_messages(
        conversation1,
        human_messages=["a1", "a2", "a3", "a4"],
        ai_messages=["r1", "r2", "r3", "r4"],
    )
    await _seed_conversation_messages(
        conversation2,
        human_messages=["b1", "b2", "b3", "b4"],
        ai_messages=["s1", "s2", "s3", "s4"],
    )

    async def update(conv):
        await user_profile_service.maybe_update_user_profile(
            db_session, user_id=user.id, conversation=conv
        )

    await asyncio.gather(update(conversation1), update(conversation2))

    # 同一用户串行意味着任意时刻只有一个更新在执行
    assert max_active == 1

    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    assert profile is not None


@pytest.mark.asyncio
async def test_profile_content_truncated_to_max_length(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    monkeypatch,
):
    """画像内容超过 500 字时应被截断。"""
    factory = _patch_deepseek_client(
        monkeypatch,
        [
            ChatResponse(content="true", model="deepseek-v4-flash"),
            ChatResponse(content="字" * 600, model="deepseek-v4-flash"),
        ],
    )

    user = await _create_user(db_session, "profile_user_7")
    conversation = await _create_conversation(db_session, user)
    await _seed_conversation_messages(
        conversation,
        human_messages=["msg1", "msg2", "msg3", "msg4"],
        ai_messages=["reply1", "reply2", "reply3", "reply4"],
    )

    await user_profile_service.maybe_update_user_profile(
        db_session, user_id=user.id, conversation=conversation
    )

    assert factory.call_count == 2
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    assert profile is not None
    assert len(profile.content) == 500


@pytest.mark.asyncio
async def test_profile_update_based_on_existing_profile(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    monkeypatch,
):
    """更新时应基于原有画像内容进行增删改。"""
    factory = _patch_deepseek_client(
        monkeypatch,
        [
            ChatResponse(content="true", model="deepseek-v4-flash"),
            ChatResponse(content="喜欢流行音乐和摇滚音乐。", model="deepseek-v4-flash"),
        ],
    )

    user = await _create_user(db_session, "profile_user_8")
    existing = UserProfile(user_id=user.id, content="喜欢流行音乐。")
    db_session.add(existing)
    await db_session.commit()

    conversation = await _create_conversation(db_session, user)
    await _seed_conversation_messages(
        conversation,
        human_messages=["msg1", "msg2", "msg3", "msg4"],
        ai_messages=["reply1", "reply2", "reply3", "reply4"],
    )

    await user_profile_service.maybe_update_user_profile(
        db_session, user_id=user.id, conversation=conversation
    )

    assert factory.call_count == 2
    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    assert profile is not None
    assert "摇滚音乐" in profile.content


@pytest.mark.asyncio
async def test_profile_updated_via_send_message(
    db_session: AsyncSession,
    fake_ai_checkpointer,
    fake_deepseek_client,
    fake_title_generator,
    monkeypatch,
):
    """通过 send_message 发送 4 条消息后，应触发画像更新。"""
    factory = _patch_deepseek_client(
        monkeypatch,
        [
            # send_message 使用 chat_stream 生成回复，不消耗 responses。
            # 此处仅提供 judge + update 两个 chat 调用的响应。
            ChatResponse(content="true", model="deepseek-v4-flash"),
            ChatResponse(content="喜欢古典音乐。", model="deepseek-v4-flash"),
        ],
    )

    user = await _create_user(db_session, "profile_user_9")
    conversation = await _create_conversation(db_session, user)

    for i in range(4):
        await ai_conversation_service.send_message(
            db_session,
            user_id=user.id,
            conversation=conversation,
            content=f"消息 {i + 1}",
        )

    result = await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    assert profile is not None
    assert "喜欢古典音乐" in profile.content


class TestProfileHelpers:
    """测试内部辅助函数。"""

    def test_extract_conversation_messages_keeps_order(self):
        """提取 Human + AI 消息时应保持顺序并排除 System。"""
        messages = [
            HumanMessage(content="你好"),
            AIMessage(content="你好！"),
            HumanMessage(content="推荐一首歌"),
            AIMessage(content="推荐《渡口》"),
        ]
        result = user_profile_service._extract_conversation_messages(messages)
        assert [type(m).__name__ for m in result] == [
            "HumanMessage",
            "AIMessage",
            "HumanMessage",
            "AIMessage",
        ]

    def test_count_human_messages(self):
        messages = [
            HumanMessage(content="a"),
            AIMessage(content="b"),
            HumanMessage(content="c"),
        ]
        assert user_profile_service._count_human_messages(messages) == 2

    def test_sanitize_profile_content_trims_and_truncates(self):
        assert user_profile_service._sanitize_profile_content("  hello  ") == "hello"
        assert len(user_profile_service._sanitize_profile_content("x" * 600)) == 500
