"""AI 结构化附件的 checkpoint 投影与 SSE 协议测试。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from echomemory_backend.ai.graphs.conversation.builder import build_graph
from echomemory_backend.services.ai_conversation_service import (
    _project_messages_for_view,
)


def test_user_message_projection_attaches_tool_artifact_to_final_ai_message():
    artifact = {
        "version": 1,
        "type": "music_card",
        "items": [{"id": 12, "title": "回声"}],
    }
    messages = [
        HumanMessage(content="推荐音乐"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "push_music_cards",
                    "args": {"resource_ids": [12]},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="已推送 1 首音乐。",
            artifact=artifact,
            tool_call_id="call-1",
            name="push_music_cards",
        ),
        AIMessage(content="这首歌适合现在听。"),
    ]

    projected = _project_messages_for_view(
        messages,
        message_types={"human", "ai"},
        include_intermediate_ai=False,
    )

    assert [item["role"] for item in projected] == ["human", "ai"]
    assert projected[-1]["attachments"] == [artifact]


def test_projection_does_not_expose_non_public_tool_artifacts():
    messages = [
        HumanMessage(content="查询"),
        ToolMessage(
            content="内部结果",
            artifact={"type": "sql_debug", "query": "secret"},
            tool_call_id="call-1",
            name="debug",
        ),
        AIMessage(content="完成"),
    ]

    projected = _project_messages_for_view(
        messages,
        message_types={"human", "ai"},
        include_intermediate_ai=False,
    )

    assert projected[-1].get("attachments", []) == []


async def test_tool_artifact_survives_langgraph_checkpoint_round_trip(
    fake_ai_checkpointer,
):
    graph = build_graph()
    config = {"configurable": {"thread_id": "attachment-round-trip"}}
    artifact = {
        "version": 1,
        "type": "album_card",
        "items": [{"id": 5, "title": "长久回声"}],
    }
    await graph.aupdate_state(
        config,
        {
            "messages": [
                HumanMessage(content="推荐专辑"),
                ToolMessage(
                    content="已推送专辑",
                    artifact=artifact,
                    tool_call_id="call-persist",
                    name="push_album_cards",
                ),
                AIMessage(content="已经为你放在这里。"),
            ],
            "user_id": 1,
            "read_only": False,
            "confirmation_token": None,
        },
    )

    state = await graph.aget_state(config)
    messages = list(state.values["messages"])
    projected = _project_messages_for_view(
        messages,
        message_types={"human", "ai"},
        include_intermediate_ai=False,
    )

    assert projected[-1]["attachments"] == [artifact]
