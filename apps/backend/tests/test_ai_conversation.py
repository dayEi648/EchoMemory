"""AI 对话接口与存储机制测试。

使用 MemorySaver 替代 Postgres Checkpointer，使用 Fake DeepSeekClient 替代真实 LLM。
"""

import json

import pytest
from fastapi.testclient import TestClient

from echomemory_backend.ai.llm import _filter_llm_messages
from echomemory_backend.core.config import settings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

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
    return resp.json()["access_token"]


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
        data = resp.json()
        assert data["conversation"]["title"] == "新对话"
        assert data["conversation"]["model"] == "deepseek-v4-flash"
        assert data["ai_message"] is None

    async def test_create_conversation_with_first_message(self, client: TestClient):
        """附带首条消息时应返回 AI 回复。"""
        token = _register_and_login(client, "ai_user_2")
        resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"first_message": "你好"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["conversation"]["title"] == "新对话"
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
        assert resp.json()["conversation"]["model"] == "deepseek-v4-pro"


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
        data = resp.json()
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
        assert resp.json()["total"] == 0
        assert len(resp.json()["items"]) == 0


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
        conversation_id = create_resp.json()["conversation"]["id"]

        resp = client.post(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"content": "今天天气如何？", "stream": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "ai"
        assert "你好，我是 AI 助手。" in data["content"]

    async def test_get_messages(self, client: TestClient):
        """应能读取会话中的完整消息列表。"""
        token = _register_and_login(client, "ai_user_5")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"first_message": "你好"},
        )
        conversation_id = create_resp.json()["conversation"]["id"]

        resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        messages = data["messages"]
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "human" in roles
        assert "ai" in roles

    async def test_stream_message(self, client: TestClient):
        """流式发送消息应返回 SSE 事件流。"""
        token = _register_and_login(client, "ai_user_6")
        create_resp = client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        conversation_id = create_resp.json()["conversation"]["id"]

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
                events.append(json.loads(line[len(prefix):]))

        content_parts = [e["data"] for e in events if e["type"] == "content"]
        assert "".join(content_parts) == "你好，我是 AI 助手。"
        assert any(e["type"] == "done" for e in events)


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
        conversation_id = create_resp.json()["conversation"]["id"]

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
        conversation_id = create_resp.json()["conversation"]["id"]

        resp = client.delete(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

        resp = client.get(
            f"{AI_CONVERSATIONS_URL}/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestAICache:
    """测试 Redis 缓存行为。"""

    async def test_conversation_list_cache_hit(self, client: TestClient, fake_ai_cache):
        """第二次获取会话列表应从缓存命中。"""
        token = _register_and_login(client, "ai_user_cache")
        client.post(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        # 第一次查询会写入缓存
        resp1 = client.get(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp1.status_code == 200
        assert fake_ai_cache.get(f"list:{resp1.json()['items'][0]['user_id']}") is not None

        # 第二次查询从缓存读取，结果一致
        resp2 = client.get(
            AI_CONVERSATIONS_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200
        assert resp2.json() == resp1.json()


class TestContextTrimming:
    """测试上下文截断逻辑。"""

    def test_filter_llm_messages_keeps_system_and_recent(self):
        """应保留系统消息与最近 N 条非工具消息。"""
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
            assert "tool" not in roles
            assert len(result) == 4  # system + 3 recent
            assert result[1].content == "msg2"
            assert result[-1].content == "msg4"
        finally:
            settings.ai_max_context_messages = original_max

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
