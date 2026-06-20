"""用户画像服务。

根据用户与 AI 的对话历史，周期性地评估并更新用户画像。
画像为自然语言文本，长度不超过 500 字，每个用户维护一条记录。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.ai.clients.deepseek import ChatMessage, DeepSeekClient
from echomemory_backend.ai.graphs.conversation.builder import build_graph
from echomemory_backend.core.config import settings
from echomemory_backend.models.ai_conversation import AIConversation
from echomemory_backend.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

# 每达到该条数的人类消息时触发一次画像更新评估
_PROFILE_EVAL_INTERVAL = 4

# 小模型判断时最多重试次数
_MAX_JUDGE_RETRIES = 3

# 画像内容最大长度（字）
_MAX_PROFILE_LENGTH = 500

# 按 user_id 维护的异步锁，保证同一用户的画像更新串行执行
_profile_update_locks: dict[int, asyncio.Lock] = {}


_JUDGE_PROMPT_TEMPLATE = """你正在维护一个用户的长期画像。请判断下面这段用户与 AI 的对话中，是否包含值得记录到用户画像中的信息。

值得记录的信息包括：用户的兴趣爱好、职业、常用设备/平台、音乐偏好、性格特点、明确表达的需求或目标、重要的背景信息等。如果只是普通寒暄、无需记忆的闲聊，则不需要记录。

注意：
- 只输出 true 或 false，不要输出任何其他内容。
- true 表示有值得记录的信息。
- false 表示没有值得记录的信息。

用户消息：
{human_messages}
"""


_UPDATE_PROMPT_TEMPLATE = """你正在维护一个用户的长期画像。请根据以下信息，更新用户的画像。

要求：
- 在原有画像的基础上增加、删除或修改内容。
- 保持精确、简洁，只记录对用户长期服务和个性化有帮助的关键信息。
- 输出内容必须为一段自然语言文本，字数严格控制在 500 字以内。
- 如果原有画像为空，则根据对话生成新的画像。
- 不要输出 XML 标签、JSON 格式、编号列表或任何额外说明，只输出画像文本本身。

当前用户画像：
{current_profile}

当前会话中的对话历史（按时间顺序）：
{conversation_history}

请输出更新后的用户画像：
"""


def _get_profile_lock(user_id: int) -> asyncio.Lock:
    """获取指定用户的画像更新锁。

    同一用户的所有会话共享同一把锁，确保画像更新串行执行。
    """
    if user_id not in _profile_update_locks:
        _profile_update_locks[user_id] = asyncio.Lock()
    return _profile_update_locks[user_id]


def _format_messages_for_judge(human_messages: list[HumanMessage]) -> str:
    """把 human 消息格式化为用于判断的文本。"""
    lines: list[str] = []
    for index, message in enumerate(human_messages, start=1):
        content = message.content
        if isinstance(content, list):
            content = "\n".join(str(block) for block in content)
        lines.append(f"{index}. {content}")
    return "\n".join(lines)


def _format_messages_for_update(messages: list[BaseMessage]) -> str:
    """把 HumanMessage + AIMessage 格式化为用于更新画像的对话历史文本。"""
    lines: list[str] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            role = "用户"
        elif isinstance(message, AIMessage):
            role = "AI"
        else:
            continue
        content = message.content
        if isinstance(content, list):
            content = "\n".join(str(block) for block in content)
        lines.append(f"{role}：{content}")
    return "\n".join(lines)


def _count_human_messages(messages: list[BaseMessage]) -> int:
    """统计消息列表中的 HumanMessage 数量。"""
    return sum(1 for message in messages if isinstance(message, HumanMessage))


def _extract_conversation_messages(
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """提取 HumanMessage 和 AIMessage，并保持原有顺序。"""
    return [
        message
        for message in messages
        if isinstance(message, (HumanMessage, AIMessage))
    ]


def _sanitize_profile_content(content: str) -> str:
    """清理模型返回的画像内容。

    - 去除首尾空白
    - 截断至最大长度
    """
    cleaned = content.strip()
    if len(cleaned) > _MAX_PROFILE_LENGTH:
        cleaned = cleaned[:_MAX_PROFILE_LENGTH]
    return cleaned


async def _get_or_create_profile(
    db: AsyncSession, user_id: int
) -> UserProfile:
    """获取或创建指定用户的画像记录。"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile(user_id=user_id, content="")
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
    return profile


async def _judge_worth_recording(
    human_messages: list[HumanMessage],
    model: str = "deepseek-v4-flash",
) -> bool:
    """使用小模型判断当前 human 消息中是否有值得记录的信息。

    模型只应输出 true 或 false。若输出其他内容，最多重试 3 次。
    """
    if not human_messages:
        return False

    client = DeepSeekClient(model=model, enable_thinking=False)
    prompt = _JUDGE_PROMPT_TEMPLATE.format(
        human_messages=_format_messages_for_judge(human_messages)
    )

    for attempt in range(1, _MAX_JUDGE_RETRIES + 1):
        try:
            response = await client.chat(
                [ChatMessage(role="system", content=prompt)],
                temperature=0.3,
            )
            answer = (response.content or "").strip().lower()
            if answer == "true":
                return True
            if answer == "false":
                return False
            logger.warning(
                "Profile judge returned non-boolean answer on attempt %d: %s",
                attempt,
                response.content,
            )
        except Exception:
            logger.exception("Profile judge failed on attempt %d", attempt)

    logger.warning(
        "Profile judge exceeded max retries (%d), treating as false",
        _MAX_JUDGE_RETRIES,
    )
    return False


async def _update_profile_content(
    current_profile: str,
    conversation_messages: list[BaseMessage],
    model: str = "deepseek-v4-flash",
) -> str:
    """使用小模型基于原画像和对话历史生成新的画像内容。"""
    client = DeepSeekClient(model=model, enable_thinking=False)
    prompt = _UPDATE_PROMPT_TEMPLATE.format(
        current_profile=current_profile or "（暂无画像）",
        conversation_history=_format_messages_for_update(conversation_messages),
    )

    response = await client.chat(
        [ChatMessage(role="system", content=prompt)],
        temperature=0.5,
    )
    return _sanitize_profile_content(response.content or "")


async def _load_conversation_messages(
    conversation: AIConversation,
) -> list[BaseMessage]:
    """从 LangGraph checkpoint 加载会话的完整消息列表。"""
    graph = build_graph(conversation.model)
    config = {
        "configurable": {"thread_id": conversation.thread_id},
        "recursion_limit": settings.ai_tool_recursion_limit,
    }
    state = await graph.aget_state(config)
    if state is None:
        return []
    return list(state.values.get("messages", []))


async def maybe_update_user_profile(
    db: AsyncSession,
    user_id: int,
    conversation: AIConversation,
) -> None:
    """根据当前会话消息，评估并可能更新用户画像。

    当会话中 human 消息数量达到 4 的倍数时触发评估；
    若小模型判断有值得记录的信息，则基于当前会话所有 Human+AI 消息更新画像。
    同一用户的更新操作会排队串行执行。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 当前用户 ID。
        conversation: 当前 AI 会话。
    """
    messages = await _load_conversation_messages(conversation)
    human_count = _count_human_messages(messages)

    if human_count == 0 or human_count % _PROFILE_EVAL_INTERVAL != 0:
        return

    lock = _get_profile_lock(user_id)
    async with lock:
        # 在锁内重新读取消息，避免排队期间消息已变化
        messages = await _load_conversation_messages(conversation)
        human_count = _count_human_messages(messages)
        if human_count == 0 or human_count % _PROFILE_EVAL_INTERVAL != 0:
            return

        human_messages = [
            message for message in messages if isinstance(message, HumanMessage)
        ]
        worth_recording = await _judge_worth_recording(human_messages)
        if not worth_recording:
            logger.debug(
                "No profile-worthy information for user %s in conversation %s",
                user_id,
                conversation.id,
            )
            return

        conversation_messages = _extract_conversation_messages(messages)
        profile = await _get_or_create_profile(db, user_id)
        new_content = await _update_profile_content(
            profile.content, conversation_messages
        )

        if not new_content:
            logger.warning(
                "Generated empty profile content for user %s, skipping update",
                user_id,
            )
            return

        profile.content = new_content
        await db.commit()
        logger.info(
            "Updated user profile for user %s (conversation %s)",
            user_id,
            conversation.id,
        )
