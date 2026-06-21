"""DeepSeek 模型工具调用能力测试。"""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from echomemory_backend.ai import langchain as ai_langchain
from echomemory_backend.ai.clients.deepseek import ChatMessage, ChatResponse, DeepSeekClient
from echomemory_backend.ai.langchain.deepseek_chat import DeepSeekChatModel


@tool
def _mock_search(query: str) -> str:
    """模拟搜索工具。"""
    return f"search result for {query}"


def _make_fake_deepseek_client(tool_calls: list[dict] | None = None):
    """构造一个支持工具调用的 Fake DeepSeekClient。"""

    class _FakeDeepSeekClient:
        def __init__(self, model, **kwargs):
            self.model = model
            self._enable_thinking = kwargs.get("enable_thinking", False)

        async def chat(self, messages, **kwargs):
            return ChatResponse(
                content="",
                tool_calls=tool_calls,
                model=self.model,
            )

        async def chat_stream(self, messages, **kwargs):
            yield ChatResponse(
                content="",
                tool_calls=tool_calls,
                model=self.model,
            )

        def chat_sync(self, messages, **kwargs):
            return ChatResponse(
                content="",
                tool_calls=tool_calls,
                model=self.model,
            )

        def chat_stream_sync(self, messages, **kwargs):
            yield ChatResponse(
                content="",
                tool_calls=tool_calls,
                model=self.model,
            )

    return _FakeDeepSeekClient


async def test_bind_tools_produces_tool_calls(monkeypatch):
    """绑定工具后，模型返回的 AIMessage 应携带 tool_calls。"""
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "_mock_search", "arguments": '{"query": "abc"}'},
        }
    ]
    FakeClient = _make_fake_deepseek_client(tool_calls)
    monkeypatch.setattr(ai_langchain.deepseek_chat, "DeepSeekClient", FakeClient)

    model = DeepSeekChatModel(model="deepseek-v4-flash")
    model_with_tools = model.bind_tools([_mock_search])
    response = await model_with_tools.ainvoke([HumanMessage(content="搜索 abc")])

    assert response.tool_calls
    assert response.tool_calls[0]["name"] == "_mock_search"
    assert response.tool_calls[0]["args"] == {"query": "abc"}


async def test_tool_messages_preserved_in_context(monkeypatch):
    """ToolMessage 应被保留并透传给底层客户端。"""
    FakeClient = _make_fake_deepseek_client([])
    monkeypatch.setattr(ai_langchain.deepseek_chat, "DeepSeekClient", FakeClient)

    from echomemory_backend.ai.langchain.deepseek_chat import _filter_llm_messages

    messages = [
        HumanMessage(content="hi"),
        ToolMessage(content="tool result", tool_call_id="call_1", name="_mock_search"),
    ]
    chat_messages = _filter_llm_messages(messages)

    assert len(chat_messages) == 2
    assert chat_messages[1].role == "tool"
    assert chat_messages[1].tool_call_id == "call_1"


async def test_assistant_tool_calls_preserved_in_context(monkeypatch):
    """assistant 的 tool_calls 必须回传，否则后续 ToolMessage 不符合协议。"""
    FakeClient = _make_fake_deepseek_client([])
    monkeypatch.setattr(ai_langchain.deepseek_chat, "DeepSeekClient", FakeClient)

    from echomemory_backend.ai.langchain.deepseek_chat import _filter_llm_messages

    messages = [
        HumanMessage(content="搜索 abc"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "_mock_search",
                    "args": {"query": "abc"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="tool result",
            tool_call_id="call_1",
            name="_mock_search",
        ),
    ]
    chat_messages = _filter_llm_messages(messages)

    assert chat_messages[1].role == "assistant"
    assert chat_messages[1].tool_calls
    assert chat_messages[1].tool_calls[0]["function"]["name"] == "_mock_search"


async def test_context_trimming_keeps_tool_call_and_result_together(monkeypatch):
    """截断不能留下缺少 assistant tool_calls 的孤立 ToolMessage。"""
    from echomemory_backend.ai.langchain.deepseek_chat import _filter_llm_messages
    from echomemory_backend.core.config import settings

    monkeypatch.setattr(settings, "ai_max_context_messages", 1)
    messages = [
        HumanMessage(content="搜索 abc"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "_mock_search",
                    "args": {"query": "abc"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
        ToolMessage(
            content="tool result",
            tool_call_id="call_1",
            name="_mock_search",
        ),
    ]

    chat_messages = _filter_llm_messages(messages)

    assert [message.role for message in chat_messages] == ["assistant", "tool"]


async def test_bound_tools_do_not_disable_text_streaming(monkeypatch):
    """绑定工具后，普通文本回复仍应逐块流式返回。"""

    class FakeStreamingClient:
        def __init__(self, model, **kwargs):
            self.model = model
            self._enable_thinking = kwargs.get("enable_thinking", False)

        async def chat_stream(self, messages, **kwargs):
            yield ChatResponse(content="第一段", model=self.model)
            yield ChatResponse(content="第二段", model=self.model)

    monkeypatch.setattr(
        ai_langchain.deepseek_chat,
        "DeepSeekClient",
        FakeStreamingClient,
    )

    model = DeepSeekChatModel(model="deepseek-v4-flash").bind_tools([_mock_search])
    chunks = [
        chunk
        async for chunk in model.astream([HumanMessage(content="普通回答")])
    ]

    assert [chunk.content for chunk in chunks if chunk.content] == [
        "第一段",
        "第二段",
    ]


async def test_deepseek_client_streams_text_chunks_when_tools_are_enabled():
    """底层客户端启用工具时也不能把普通文本累积成单个响应。"""

    async def fake_stream():
        for content in ("第一段", "第二段"):
            yield SimpleNamespace(
                usage=None,
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=content,
                            reasoning_content=None,
                            tool_calls=None,
                        )
                    )
                ],
                model="deepseek-v4-flash",
            )

    class FakeCompletions:
        async def create(self, **kwargs):
            return fake_stream()

    client = DeepSeekClient(
        model="deepseek-v4-flash",
        api_key="test",
    )
    client._async_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    chunks = [
        chunk
        async for chunk in client.chat_stream(
            [ChatMessage(role="user", content="普通回答")],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "_mock_search",
                        "description": "mock",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )
    ]

    assert [chunk.content for chunk in chunks] == ["第一段", "第二段"]


async def test_streamed_tool_call_chunks_are_assembled(monkeypatch):
    """流式工具参数片段应由 LangChain 合并为完整 tool call。"""

    class FakeToolCallStreamingClient:
        def __init__(self, model, **kwargs):
            self.model = model
            self._enable_thinking = kwargs.get("enable_thinking", False)

        async def chat_stream(self, messages, **kwargs):
            yield ChatResponse(
                content="",
                tool_call_chunks=[
                    {
                        "index": 0,
                        "id": "call_1",
                        "name": "_mock_search",
                        "args": '{"query":',
                    }
                ],
                model=self.model,
            )
            yield ChatResponse(
                content="",
                tool_call_chunks=[
                    {
                        "index": 0,
                        "id": None,
                        "name": None,
                        "args": '"abc"}',
                    }
                ],
                model=self.model,
            )

    monkeypatch.setattr(
        ai_langchain.deepseek_chat,
        "DeepSeekClient",
        FakeToolCallStreamingClient,
    )

    model = DeepSeekChatModel(model="deepseek-v4-flash").bind_tools([_mock_search])
    chunks = [
        chunk
        async for chunk in model.astream([HumanMessage(content="搜索 abc")])
    ]
    combined = chunks[0]
    for chunk in chunks[1:]:
        combined += chunk

    assert combined.tool_calls[0]["name"] == "_mock_search"
    assert combined.tool_calls[0]["args"] == {"query": "abc"}


def test_deepseek_request_serializes_assistant_tool_calls():
    """发回工具结果时，请求中必须包含对应 assistant tool_calls。"""
    client = DeepSeekClient(model="deepseek-v4-flash", api_key="test")
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "_mock_search",
                "arguments": '{"query":"abc"}',
            },
        }
    ]

    body = client._build_request(
        [
            ChatMessage(role="user", content="搜索 abc"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=tool_calls,
                reasoning_content="先判断需要调用搜索工具。",
            ),
            ChatMessage(
                role="tool",
                content="tool result",
                tool_call_id="call_1",
                name="_mock_search",
            ),
        ],
        temperature=0.6,
        max_tokens=None,
        stream=False,
    )

    assert body["messages"][1]["tool_calls"] == tool_calls
    assert (
        body["messages"][1]["reasoning_content"]
        == "先判断需要调用搜索工具。"
    )
    assert body["messages"][2]["tool_call_id"] == "call_1"


def test_deepseek_request_adds_empty_reasoning_for_deterministic_tool_call():
    """确定性工具调用也必须满足 DeepSeek 思考模式的回传协议。"""
    client = DeepSeekClient(model="deepseek-v4-flash", api_key="test")
    tool_calls = [
        {
            "id": "confirm-1",
            "type": "function",
            "function": {
                "name": "confirm_collection_change",
                "arguments": "{}",
            },
        }
    ]

    body = client._build_request(
        [
            ChatMessage(role="user", content="我确认收藏。"),
            ChatMessage(role="assistant", content="", tool_calls=tool_calls),
            ChatMessage(
                role="tool",
                content="已完成收藏。",
                tool_call_id="confirm-1",
                name="confirm_collection_change",
            ),
        ],
        temperature=0.6,
        max_tokens=None,
        stream=False,
    )

    assert body["messages"][1]["reasoning_content"] == ""
