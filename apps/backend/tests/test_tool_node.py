"""元数据感知工具执行节点测试。"""

import asyncio

import pytest
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage

from echomemory_backend.ai.graphs.conversation.nodes.tool_node import build_tool_node
from echomemory_backend.ai.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_tool_node_rejects_tool_not_allowed_by_current_context():
    executed = False

    @tool
    async def write_tool(value: str) -> str:
        """模拟写工具。"""
        nonlocal executed
        executed = True
        return value

    registry = ToolRegistry()
    registry.register(write_tool, read_only=False)
    node = build_tool_node(registry)

    result = await node(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "write_tool",
                            "args": {"value": "x"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "user_id": 1,
            "read_only": True,
        },
        {},
    )

    assert executed is False
    assert "当前不可用" in result["messages"][0].content


@pytest.mark.asyncio
async def test_tool_node_hides_internal_exception_details():
    @tool
    async def failing_tool() -> str:
        """模拟失败工具。"""
        raise RuntimeError("secret-internal-detail")

    registry = ToolRegistry()
    registry.register(failing_tool)
    node = build_tool_node(registry)

    result = await node(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "failing_tool",
                            "args": {},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "user_id": 1,
            "read_only": False,
        },
        {},
    )

    content = result["messages"][0].content
    assert "执行失败" in content
    assert "secret-internal-detail" not in content


@pytest.mark.asyncio
async def test_tool_node_runs_batch_serially_when_parallel_is_disallowed():
    active = 0
    maximum_active = 0

    @tool
    async def serial_tool(value: int) -> int:
        """模拟必须串行的工具。"""
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return value

    registry = ToolRegistry()
    registry.register(serial_tool, allow_parallel=False)
    node = build_tool_node(registry)

    await node(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "serial_tool",
                            "args": {"value": 1},
                            "id": "call-1",
                            "type": "tool_call",
                        },
                        {
                            "name": "serial_tool",
                            "args": {"value": 2},
                            "id": "call-2",
                            "type": "tool_call",
                        },
                    ],
                )
            ],
            "user_id": 1,
            "read_only": False,
        },
        {},
    )

    assert maximum_active == 1


@pytest.mark.asyncio
async def test_tool_node_injects_authenticated_runtime_without_model_argument():
    @tool
    async def runtime_tool(runtime: ToolRuntime) -> str:
        """读取受信任运行时中的用户。"""
        return f"user:{runtime.state['user_id']}"

    registry = ToolRegistry()
    registry.register(runtime_tool)
    node = build_tool_node(registry)

    result = await node(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "runtime_tool",
                            "args": {},
                            "id": "call-runtime",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            "user_id": 42,
            "read_only": False,
        },
        {},
    )

    assert result["messages"][0].content == "user:42"
    assert "runtime" not in runtime_tool.tool_call_schema.model_json_schema()["properties"]
