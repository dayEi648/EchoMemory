"""API 统一响应信封中间件。

对 ``/api/v1`` 下除流式响应外的 JSON 成功响应自动包装为 ``{code, msg, data}``；
204 无内容响应转换为 200 且 ``data`` 为 null。错误响应由全局异常处理器直接生成信封，
本中间件仅透传已信封化的负载。
"""

import json
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from echomemory_backend.schemas.response import error_body, is_envelope, wrap_success_payload

API_V1_PREFIX = "/api/v1"
_STREAMING_MEDIA_TYPE = "text/event-stream"


def _copy_response_headers(source: Response, target: JSONResponse | Response) -> None:
    """将原响应头复制到目标响应，跳过由框架管理的头。

    Args:
        source: 原始响应。
        target: 目标响应。
    """
    for key, value in source.headers.items():
        if key.lower() in {"content-length", "content-type"}:
            continue
        target.headers[key] = value


class ApiEnvelopeMiddleware(BaseHTTPMiddleware):
    """将 REST JSON 响应统一包装为业务信封。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        """处理请求并在需要时包装响应体。

        Args:
            request: 当前 HTTP 请求。
            call_next: 下一个中间件或路由处理器。

        Returns:
            原始或包装后的 HTTP 响应。
        """
        if not request.url.path.startswith(API_V1_PREFIX):
            return await call_next(request)

        response = await call_next(request)

        if isinstance(response, StreamingResponse):
            return response

        content_type = response.headers.get("content-type", "")
        if _STREAMING_MEDIA_TYPE in content_type:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        if response.status_code == 204:
            wrapped = JSONResponse(status_code=200, content=wrap_success_payload(None))
            _copy_response_headers(response, wrapped)
            return wrapped

        if not body:
            if 200 <= response.status_code < 300:
                wrapped = JSONResponse(
                    status_code=response.status_code,
                    content=wrap_success_payload(None),
                )
                _copy_response_headers(response, wrapped)
                return wrapped
            empty = Response(
                status_code=response.status_code,
                headers=dict(response.headers),
            )
            return empty

        try:
            payload: Any = json.loads(body)
        except json.JSONDecodeError:
            passthrough = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            return passthrough

        if is_envelope(payload):
            wrapped = JSONResponse(status_code=response.status_code, content=payload)
            _copy_response_headers(response, wrapped)
            return wrapped

        if response.status_code >= 400:
            if isinstance(payload, dict) and "detail" in payload:
                detail = payload["detail"]
                msg = detail if isinstance(detail, str) else str(detail)
                wrapped = JSONResponse(
                    status_code=response.status_code,
                    content=error_body(msg, status_code=response.status_code),
                )
                _copy_response_headers(response, wrapped)
                return wrapped
            wrapped = JSONResponse(status_code=response.status_code, content=payload)
            _copy_response_headers(response, wrapped)
            return wrapped

        if 200 <= response.status_code < 300:
            wrapped = JSONResponse(
                status_code=response.status_code,
                content=wrap_success_payload(payload),
            )
            _copy_response_headers(response, wrapped)
            return wrapped

        passthrough = JSONResponse(status_code=response.status_code, content=payload)
        _copy_response_headers(response, passthrough)
        return passthrough
