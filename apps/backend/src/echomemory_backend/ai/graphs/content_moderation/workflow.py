"""固定步骤的内容审核 Agent 工作流。"""

from __future__ import annotations

import json
import re

from echomemory_backend.ai.clients.deepseek import ChatMessage, DeepSeekClient
from echomemory_backend.ai.graphs.content_moderation.prompts import (
    MODERATION_SYSTEM_PROMPT,
)
from echomemory_backend.ai.monitoring.runtime import get_current_monitor
from echomemory_backend.core.config import settings
from echomemory_backend.schemas.content_moderation import ModerationDecision

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_decision(raw: str) -> ModerationDecision:
    """从模型文本提取并严格校验审核结果。"""
    match = _JSON_BLOCK_RE.search(raw)
    if match is None:
        raise ValueError("moderation model did not return a JSON object")
    payload = json.loads(match.group(0))
    return ModerationDecision.model_validate(payload)


async def evaluate_content(
    *,
    content_type: str,
    content: str,
) -> tuple[ModerationDecision, dict | None]:
    """调用快速模型审核一段用户文本。"""
    monitor = get_current_monitor()
    user_prompt = (
        f"内容类型：{content_type}\n"
        "<untrusted_user_content>\n"
        f"{content}\n"
        "</untrusted_user_content>"
    )
    if monitor is not None:
        monitor.record_event(
            event_type="prompt.rendered",
            component_type="prompt",
            component_name="content_moderation",
            status="SUCCEEDED",
            payload={"system": MODERATION_SYSTEM_PROMPT, "user": user_prompt},
        )
        monitor.record_event(
            event_type="llm.started",
            component_type="llm",
            component_name=settings.content_moderation_model,
            status="RUNNING",
        )

    client = DeepSeekClient(
        model=settings.content_moderation_model,
        enable_thinking=False,
        timeout=settings.content_moderation_timeout_seconds,
    )
    response = await client.chat(
        [
            ChatMessage(role="system", content=MODERATION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ],
        temperature=0,
        max_tokens=300,
    )
    decision = _parse_decision(response.content)
    if monitor is not None:
        monitor.add_usage(response.usage)
        monitor.record_event(
            event_type="llm.completed",
            component_type="llm",
            component_name=response.model or settings.content_moderation_model,
            status="SUCCEEDED",
            payload={"decision": decision.model_dump()},
        )
        monitor.record_event(
            event_type="output.validated",
            component_type="schema",
            component_name="ModerationDecision",
            status="SUCCEEDED",
            payload=decision.model_dump(),
        )
    return decision, response.usage
