"""AI 对话接口与存储机制测试。

使用 MemorySaver 替代 Postgres Checkpointer，使用 Fake DeepSeekClient 替代真实 LLM。
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.ai.graphs.conversation.builder import (
    build_graph,
    get_thread_config,
)
from echomemory_backend.ai.langchain.deepseek_chat import _filter_llm_messages
from echomemory_backend.api.v1.endpoints.ai_conversation import (
    _resolve_message_view,
)
from echomemory_backend.core.config import settings
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.user import User
from echomemory_backend.services import ai_conversation_service
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from tests.api_helpers import api_data

AI_CONVERSATIONS_URL = "/api/v1/ai/conversations"


def _register_and_login(client: TestClient, username: str) -> str:
    """注册并登录测试用户，返回 access token。"""
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
    """在数据库中直接创建测试用户，返回 User 实例。"""
    user = User(
        username=username,
        password_hash="hashed-secret",
        nickname=username,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestAIConversationCreate:
    """测试创建 AI 对话会话。"""

    async def test_create_conversation_without_first_message(self, client: TestClient):
        """不附带首条消息时应创建空会话。"""
        token = _register_and_login(client, "ai_user_1")
        resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["conversation"]["title"] == "新对话"
        assert data["conversation"]["model"] == "deepseek-v4-flash"
        assert data["ai_message"] is None

        conversation_id = data["conversation"]["id"]
        messages_resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        messages = api_data(messages_resp)["messages"]
        assert messages == []

        forged_internal_view = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params=[("message_types", "system"), ("message_types", "tool")],
        )
        assert forged_internal_view.status_code == 200
        assert api_data(forged_internal_view)["messages"] == []

    async def test_create_conversation_with_first_message(self, client: TestClient):
        """附带首条消息时应返回 AI 回复并自动生成标题。"""
        token = _register_and_login(client, "ai_user_2")
        resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"first_message": "你好"},
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["conversation"]["title"] == "生成的标题"
        assert data["ai_message"] is not None
        assert data["ai_message"]["role"] == "ai"
        assert "你好，我是 AI 助手。" in data["ai_message"]["content"]

    async def test_create_conversation_with_custom_model(self, client: TestClient):
        """应支持创建会话时指定模型。"""
        token = _register_and_login(client, "ai_user_model")
        resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"model": "deepseek-v4-pro"},
        )
        assert resp.status_code == 201
        assert api_data(resp)["conversation"]["model"] == "deepseek-v4-pro"


class TestAIConversationList:
    """测试会话列表查询。"""

    async def test_list_conversations(self, client: TestClient):
        """应返回当前用户的会话列表。"""
        token = _register_and_login(client, "ai_user_3")
        client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        resp = client.get(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "新对话"

    async def test_list_conversations_only_own(self, client: TestClient):
        """不应返回其他用户的会话。"""
        token_a = _register_and_login(client, "ai_user_list_a")
        token_b = _register_and_login(client, "ai_user_list_b")

        client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token_a}"},
            json={},
        )
        resp = client.get(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 200
        assert api_data(resp)["total"] == 0
        assert len(api_data(resp)["items"]) == 0


class TestAIConversationMessages:
    """测试消息发送、读取与流式输出。"""

    async def test_send_message(self, client: TestClient):
        """非流式发送消息应返回 AI 回复。"""
        token = _register_and_login(client, "ai_user_4")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.post(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "今天天气如何？", "stream": False},
        )
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["role"] == "ai"
        assert "你好，我是 AI 助手。" in data["content"]

    async def test_get_messages(self, client: TestClient):
        """普通用户读取历史时只应看到 human 与最终 ai 消息。"""
        token = _register_and_login(client, "ai_user_5")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"first_message": "你好"},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = api_data(resp)
        messages = data["messages"]
        roles = [m["role"] for m in messages]
        assert roles == ["human", "ai"]

    async def test_admin_can_filter_complete_checkpoint_history(
        self,
        client: TestClient,
        db_session: AsyncSession,
    ):
        """管理员显式筛选时应能读取完整的内部消息序列。"""
        token = _register_and_login(client, "ai_admin_messages")
        user = await db_session.scalar(
            select(User).where(User.username == "ai_admin_messages")
        )
        assert user is not None
        user.role = UserRole.ADMIN
        await db_session.commit()

        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation = api_data(create_resp)["conversation"]
        graph = build_graph(conversation["model"])
        await graph.aupdate_state(
            get_thread_config(conversation["thread_id"]),
            {
                "messages": [
                    HumanMessage(content="搜索新闻"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "search_web",
                                "args": {"query": "新闻"},
                                "id": "call-1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    ToolMessage(
                        content=[{"type": "text", "text": "# 搜索结果"}],
                        tool_call_id="call-1",
                        name="search_web",
                    ),
                    AIMessage(content="最终回答"),
                ]
            },
        )

        resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation['id']}/messages",
            headers={"Authorization": f"Bearer {token}"},
            params=[
                ("message_types", "system"),
                ("message_types", "human"),
                ("message_types", "ai"),
                ("message_types", "tool"),
            ],
        )

        assert resp.status_code == 200
        messages = api_data(resp)["messages"]
        assert [message["role"] for message in messages] == [
            "system",
            "human",
            "ai",
            "tool",
            "ai",
        ]
        assert messages[2]["tool_calls"][0]["name"] == "search_web"
        assert messages[3]["tool_call_id"] == "call-1"

    async def test_stream_message(self, client: TestClient):
        """流式发送消息应返回 SSE 事件流。"""
        token = _register_and_login(client, "ai_user_6")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.post(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "你好", "stream": True},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = []
        for line in resp.text.split("\n\n"):
            if not line.strip():
                continue
            prefix = "data: "
            if line.startswith(prefix):
                events.append(json.loads(line[len(prefix) :]))

        content_parts = [e["data"] for e in events if e["type"] == "content"]
        reasoning_parts = [e["data"] for e in events if e["type"] == "reasoning"]
        assert "".join(content_parts) == "你好，我是 AI 助手。"
        assert "".join(reasoning_parts) == "先理解用户的问候，再简洁回应。"
        assert any(e["type"] == "done" for e in events)

        messages_resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        messages = api_data(messages_resp)["messages"]
        assert [message["role"] for message in messages] == ["human", "ai"]
        assert messages[-1]["content"] == "你好，我是 AI 助手。"
        assert messages[-1]["reasoning_content"] == "先理解用户的问候，再简洁回应。"


class TestAIConversationSecurity:
    """测试会话访问权限隔离。"""

    async def test_cannot_access_other_user_conversation(self, client: TestClient):
        """用户不能访问或操作其他用户的会话。"""
        token_a = _register_and_login(client, "ai_user_sec_a")
        token_b = _register_and_login(client, "ai_user_sec_b")

        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token_a}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404

        resp = client.post(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"content": "你好", "stream": False},
        )
        assert resp.status_code == 404

        resp = client.delete(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 404

    async def test_nonexistent_conversation_returns_404(self, client: TestClient):
        """访问不存在的会话应返回 404。"""
        token = _register_and_login(client, "ai_user_404")

        resp = client.get(
            f"{AI_CONVERSATIONS_URL}/999999/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

        resp = client.post(
            f"{AI_CONVERSATIONS_URL}/999999/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "你好", "stream": False},
        )
        assert resp.status_code == 404


class TestAIConversationDelete:
    """测试删除会话。"""

    async def test_delete_conversation(self, client: TestClient):
        """删除后应无法再通过接口访问会话。"""
        token = _register_and_login(client, "ai_user_7")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.delete(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestContextTrimming:
    """测试上下文截断逻辑。"""

    def test_filter_llm_messages_keeps_system_and_recent(self):
        """应保留系统消息与最近 N 条消息（含工具消息）。"""
        original_max = settings.ai_max_context_messages
        settings.ai_max_context_messages = 3
        try:
            messages = [
                SystemMessage(content="system"),
                HumanMessage(content="msg1"),
                AIMessage(content="msg2"),
                HumanMessage(content="msg3"),
                AIMessage(content="msg4"),
                ToolMessage(content="tool", tool_call_id="tc1", name="tool"),
            ]
            result = _filter_llm_messages(messages)
            roles = [m.role for m in result]
            assert roles[0] == "system"
            assert "tool" in roles
            assert len(result) == 4  # system + 3 recent (human, ai, tool)
            assert result[1].content == "msg3"
            assert result[-1].content == "tool"
        finally:
            settings.ai_max_context_messages = original_max


class TestConversationMessageViews:
    """测试会话历史的用户视图与管理员调试视图。"""

    def test_user_view_hides_system_tool_and_tool_call_ai_messages(self):
        messages = [
            SystemMessage(content="system"),
            HumanMessage(content="搜索新闻"),
            AIMessageChunk(
                content="",
                tool_calls=[
                    {
                        "name": "search_web",
                        "args": {"query": "新闻"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content=[{"type": "text", "text": "# 搜索结果"}],
                tool_call_id="call-1",
                name="search_web",
            ),
            AIMessage(content="这是搜索后的自然语言回答。"),
        ]

        filtered = ai_conversation_service._filter_messages_for_view(
            messages,
            message_types={"human", "ai"},
            include_intermediate_ai=False,
        )

        assert [message.type for message in filtered] == ["human", "ai"]
        assert filtered[-1].content == "这是搜索后的自然语言回答。"

    def test_admin_view_can_select_all_message_types(self):
        messages = [
            SystemMessage(content="system"),
            HumanMessage(content="hello"),
            AIMessage(content="", tool_calls=[{
                "name": "search_web",
                "args": {"query": "hello"},
                "id": "call-1",
                "type": "tool_call",
            }]),
            ToolMessage(content="result", tool_call_id="call-1", name="search_web"),
            AIMessage(content="answer"),
        ]

        filtered = ai_conversation_service._filter_messages_for_view(
            messages,
            message_types={"system", "human", "ai", "tool"},
            include_intermediate_ai=True,
        )

        assert [message.type for message in filtered] == [
            "system",
            "human",
            "ai",
            "tool",
            "ai",
        ]

    def test_normal_user_cannot_request_internal_message_types(self):
        message_types, include_intermediate = _resolve_message_view(
            UserRole.USER,
            ["system", "tool"],
        )

        assert message_types == {"human", "ai"}
        assert include_intermediate is False

    def test_admin_can_request_internal_message_types(self):
        message_types, include_intermediate = _resolve_message_view(
            UserRole.ADMIN,
            ["system", "tool"],
        )

        assert message_types == {"system", "tool"}
        assert include_intermediate is True

    def test_admin_without_filter_uses_safe_conversation_view(self):
        message_types, include_intermediate = _resolve_message_view(
            UserRole.SUPER_ADMIN,
            None,
        )

        assert message_types == {"human", "ai"}
        assert include_intermediate is False

    def test_filter_llm_messages_no_system(self):
        """无系统消息时仅截断最近 N 条非工具消息。"""
        original_max = settings.ai_max_context_messages
        settings.ai_max_context_messages = 2
        try:
            messages = [
                HumanMessage(content="msg1"),
                AIMessage(content="msg2"),
                HumanMessage(content="msg3"),
            ]
            result = _filter_llm_messages(messages)
            assert len(result) == 2
            assert result[0].content == "msg2"
            assert result[1].content == "msg3"
        finally:
            settings.ai_max_context_messages = original_max

    def test_filter_llm_messages_drops_assistant_output_before_first_user_message(self):
        """历史遗留的无用户输入 AI 消息不应进入后续模型上下文。"""
        messages = [
            SystemMessage(content="system"),
            AIMessage(content="做一个音乐推荐卡来介绍自己"),
            HumanMessage(content="你好"),
            AIMessage(content="你好，我是 AI 助手。"),
        ]

        result = _filter_llm_messages(messages)

        assert [message.role for message in result] == ["system", "user", "assistant"]
        assert all("音乐推荐卡" not in message.content for message in result)


def test_remove_orphan_assistant_messages_from_history():
    """消息历史不应向前端返回首条用户消息之前的 AI 输出。"""
    messages = [
        SystemMessage(content="system"),
        AIMessage(content="做一个音乐推荐卡来介绍自己"),
        HumanMessage(content="你好"),
        AIMessage(content="你好，我是 AI 助手。"),
    ]

    filtered = ai_conversation_service._remove_orphan_assistant_messages(messages)

    assert [message.type for message in filtered] == ["system", "human", "ai"]


def test_message_to_dict_sanitizes_legacy_tagged_ai_content():
    """旧 checkpoint 中的标签协议不应再暴露给前端。"""
    message = AIMessage(
        content="<thinking>分析用户意图</thinking><answer>最终回答<answer>"
    )

    result = ai_conversation_service._message_to_dict(message)

    assert result["content"] == "最终回答"
    assert result["reasoning_content"] == "分析用户意图"


class TestAIConversationServiceSecurity:
    """测试 AI 对话服务层的权限校验与状态用户隔离。"""

    async def test_send_message_rejects_wrong_user_id(
        self,
        db_session: AsyncSession,
        fake_ai_checkpointer,
        fake_deepseek_client,
    ):
        """服务层显式校验 user_id，禁止用他人身份发送消息。"""
        owner = await _create_user(db_session, "owner")
        attacker = await _create_user(db_session, "attacker")
        conversation, _ = await ai_conversation_service.create_conversation(
            db_session, user_id=owner.id, title="owner-conv"
        )

        with pytest.raises(BusinessError) as exc_info:
            await ai_conversation_service.send_message(
                db_session,
                user_id=attacker.id,
                conversation=conversation,
                content="你好",
            )
        assert exc_info.value.status_code == 403


class TestAIConversationTitle:
    """测试会话标题自动生成与手动更新。"""

    async def test_title_auto_generated_after_non_stream_first_message(
        self, client: TestClient
    ):
        """非流式首条消息后，标题应自动更新。"""
        token = _register_and_login(client, "ai_user_title_1")
        resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"first_message": "推荐一首歌"},
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["conversation"]["title"] == "生成的标题"

    async def test_title_not_changed_without_user_message(self, client: TestClient):
        """仅创建空会话时，标题应保持默认值。"""
        token = _register_and_login(client, "ai_user_title_2")
        resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["conversation"]["title"] == "新对话"

    async def test_title_generated_after_stream_first_message(self, client: TestClient):
        """流式首条消息后，标题应在异步生成后更新。"""
        token = _register_and_login(client, "ai_user_title_3")
        resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"first_message": "你好", "stream": True},
        )
        assert resp.status_code == 200
        # 消费完流式响应
        for _ in resp.iter_text():
            pass

        # 异步标题生成完成后，列表接口应返回新标题
        list_resp = client.get(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_resp.status_code == 200
        items = api_data(list_resp)["items"]
        assert len(items) == 1
        assert items[0]["title"] == "生成的标题"

    async def test_manual_update_title(self, client: TestClient):
        """应支持手动更新会话标题。"""
        token = _register_and_login(client, "ai_user_title_4")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.patch(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "我的自定义标题"},
        )
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["title"] == "我的自定义标题"

    async def test_manual_update_title_too_long(self, client: TestClient):
        """标题超长时应返回 422。"""
        token = _register_and_login(client, "ai_user_title_5")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.patch(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "x" * 201},
        )
        assert resp.status_code == 422

    async def test_cannot_update_other_user_title(self, client: TestClient):
        """不能修改其他用户的会话标题。"""
        token_a = _register_and_login(client, "ai_user_title_6")
        token_b = _register_and_login(client, "ai_user_title_7")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token_a}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        resp = client.patch(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"title": "恶意标题"},
        )
        assert resp.status_code == 404

    async def test_manual_title_prevents_auto_generation(self, client: TestClient):
        """手动设置标题后，首条消息不再触发自动标题生成。"""
        token = _register_and_login(client, "ai_user_title_8")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation_id = api_data(create_resp)["conversation"]["id"]

        client.patch(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "预设标题"},
        )

        resp = client.post(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "你好", "stream": False},
        )
        assert resp.status_code == 200

        list_resp = client.get(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        items = api_data(list_resp)["items"]
        assert items[0]["title"] == "预设标题"


def test_sanitize_title_trims_and_falls_back():
    """标题清理应去除引号并回退默认标题。"""
    from echomemory_backend.services.ai_conversation_service import _sanitize_title

    assert _sanitize_title('  "自定义标题"  ') == "自定义标题"
    assert _sanitize_title("   ") == "新对话"
    assert _sanitize_title("x" * 250) == "x" * 200
