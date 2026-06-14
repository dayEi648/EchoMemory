"""统一 API 响应信封测试。"""

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.responses import Response

from echomemory_backend.main import app
from tests.api_helpers import api_body, api_data, api_error, api_msg

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


@pytest.fixture(scope="module", autouse=True)
def envelope_test_routes():
    """临时挂载用于测试中间件各分支的端点，测试结束后清理。"""

    async def _headers():
        return JSONResponse({"ok": True}, headers={"x-custom-header": "preserved"})

    async def _raw_error():
        return Response(
            content='{"detail":"raw error"}',
            status_code=400,
            media_type="application/json",
        )

    async def _raw_error_no_detail():
        return JSONResponse({"error": "raw error"}, status_code=400)

    async def _plain():
        return PlainTextResponse("plain text")

    async def _empty():
        return Response(status_code=200)

    async def _generic_exc():
        raise RuntimeError("boom")

    async def _http_exc_non_str():
        raise HTTPException(status_code=400, detail={"field": "bad"})

    async def _skip():
        return {"code": 0, "msg": "raw"}

    route_defs = [
        ("/api/v1/__test_headers", ["GET"], _headers),
        ("/api/v1/__test_raw_error", ["GET"], _raw_error),
        ("/api/v1/__test_raw_error_no_detail", ["GET"], _raw_error_no_detail),
        ("/api/v1/__test_plain", ["GET"], _plain),
        ("/api/v1/__test_empty", ["GET"], _empty),
        ("/api/v1/__test_exc", ["GET"], _generic_exc),
        ("/api/v1/__test_http_exc", ["GET"], _http_exc_non_str),
        ("/__test_skip", ["GET"], _skip),
    ]

    added = []
    for path, methods, endpoint in route_defs:
        route = APIRoute(path=path, endpoint=endpoint, methods=methods)
        app.router.routes.append(route)
        added.append(route)

    yield

    for route in added:
        try:
            app.router.routes.remove(route)
        except ValueError:
            pass


class TestApiEnvelope:
    """验证成功与失败响应均符合 {code, msg, data} 信封。"""

    async def test_success_response_envelope(self, client: TestClient):
        """成功响应应包含 code=0 与 data 负载。"""
        client.post(
            REGISTER_URL,
            data={"username": "env_user", "password": "secret123", "nickname": "Env"},
        )
        resp = client.post(
            LOGIN_URL,
            json={"username": "env_user", "password": "secret123"},
        )
        body = resp.json()
        assert body["code"] == 0
        assert body["msg"] == "success"
        assert "access_token" in body["data"]
        assert api_data(resp)["access_token"] == body["data"]["access_token"]

    async def test_error_response_envelope(self, client: TestClient):
        """失败响应应包含非 0 code 与 null data。"""
        resp = client.post(
            LOGIN_URL,
            json={"username": "nobody", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        body = api_error(resp)
        assert body["code"] == 40101
        assert body["data"] is None
        assert api_msg(resp) == body["msg"]

    async def test_void_success_envelope(self, client: TestClient):
        """原 204 无内容操作应返回 200 且 data 为 null。"""
        reg = client.post(
            REGISTER_URL,
            data={"username": "void_user", "password": "secret123", "nickname": "Void"},
        )
        token = api_data(reg)["access_token"]
        resp = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            json={"refresh_token": api_data(reg)["refresh_token"]},
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

    async def test_non_api_v1_path_skipped(self, client: TestClient):
        """/api/v1 之外的请求不应被包装。"""
        resp = client.get("/__test_skip")
        assert resp.status_code == 200
        assert api_body(resp) == {"code": 0, "msg": "raw"}

    async def test_success_response_preserves_custom_header(self, client: TestClient):
        """包装成功响应时应保留原始响应中的自定义头。"""
        resp = client.get("/api/v1/__test_headers")
        assert resp.status_code == 200
        assert resp.headers["x-custom-header"] == "preserved"
        assert api_data(resp)["ok"] is True

    async def test_raw_error_response_with_detail_is_wrapped(self, client: TestClient):
        """对于直接返回 {detail: ...} 的原始错误响应，中间件应补包成信封。"""
        resp = client.get("/api/v1/__test_raw_error")
        assert resp.status_code == 400
        body = api_error(resp)
        assert body["code"] == 40001
        assert body["data"] is None
        assert api_msg(resp) == "raw error"

    async def test_raw_error_response_without_detail_passes_through(
        self, client: TestClient
    ):
        """状态码 >=400 但负载不含 detail 的 JSON 响应应直接透传。"""
        resp = client.get("/api/v1/__test_raw_error_no_detail")
        assert resp.status_code == 400
        assert resp.json() == {"error": "raw error"}

    async def test_non_json_body_passes_through(self, client: TestClient):
        """非 JSON 响应体应直接透传，不做包装。"""
        resp = client.get("/api/v1/__test_plain")
        assert resp.status_code == 200
        assert resp.text == "plain text"
        assert "text/plain" in resp.headers.get("content-type", "")

    async def test_empty_body_success_envelope(self, client: TestClient):
        """无内容的成功响应应包装为 data=null 的信封。"""
        resp = client.get("/api/v1/__test_empty")
        assert resp.status_code == 200
        assert api_data(resp) is None

    async def test_generic_exception_returns_500_envelope(self):
        """未捕获异常应被兜底处理器转换为 500 信封。

        TestClient 默认会在应用抛出未处理异常时重新抛出，因此使用
        ``raise_server_exceptions=False`` 来验证兜底处理器返回的响应。
        """
        with TestClient(app, raise_server_exceptions=False) as subclient:
            resp = subclient.get("/api/v1/__test_exc")
        assert resp.status_code == 500
        body = api_error(resp)
        assert body["code"] == 50001
        assert "Internal server error" in api_msg(resp)

    async def test_http_exception_with_non_string_detail(self, client: TestClient):
        """HTTPException 的 detail 为非字符串时，应被序列化为字符串。"""
        resp = client.get("/api/v1/__test_http_exc")
        assert resp.status_code == 400
        body = api_error(resp)
        assert body["code"] == 40001
        assert api_msg(resp) == str({"field": "bad"})

    async def test_validation_error_envelope(self, client: TestClient):
        """请求参数校验失败应返回 422 信封。"""
        resp = client.post(
            LOGIN_URL,
            json={"username": "env_val_user", "password": "short"},
        )
        assert resp.status_code == 422
        body = api_error(resp)
        assert body["code"] == 42201
        assert body["data"] is None

    async def test_openapi_and_docs_disabled(self, client: TestClient):
        """后端不再自动生成 Swagger / ReDoc / openapi.json。"""
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404
