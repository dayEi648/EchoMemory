"""在请求生命周期内收集日志上下文（方法、路径、请求体）的中间件。"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from echomemory_backend.core.logging.context import set_log_context

MAX_REQUEST_BODY_BYTES = 8 * 1024


class LogContextMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求初始化日志上下文，供日志 Handler 读取。"""

    async def dispatch(self, request: Request, call_next):
        """在请求进入时记录请求信息，请求结束后清理上下文。"""
        context = {
            "method": request.method,
            "path": request.url.path,
        }

        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) <= MAX_REQUEST_BODY_BYTES:
                        body = await request.body()
                        context["request_body"] = body.decode("utf-8", errors="replace")
                except Exception:
                    # 请求体读取失败时不影响主流程
                    pass

        set_log_context(**context)
        return await call_next(request)
