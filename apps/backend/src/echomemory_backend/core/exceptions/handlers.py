"""全局异常处理器。

提供应用级别的统一异常处理，将业务异常、HTTP 异常、参数校验异常以及未捕获异常
统一转换为 ``{code, msg, data}`` 响应信封，避免内部细节泄露给客户端。
"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.schemas.response import error_body

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    msg: str,
    *,
    code: int | None = None,
) -> JSONResponse:
    """构造统一错误 JSON 响应。

    Args:
        status_code: HTTP 状态码。
        msg: 错误提示信息。
        code: 可选业务错误码。

    Returns:
        包含错误信封的 JSONResponse。
    """
    return JSONResponse(
        status_code=status_code,
        content=error_body(msg, status_code=status_code, code=code),
    )


async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    """将业务异常统一转换为 JSON 响应信封。

    Args:
        request: 当前请求对象。
        exc: 抛出的 BusinessError 实例。

    Returns:
        包含业务错误信封的 JSONResponse。
    """
    return _error_response(exc.status_code, exc.detail, code=exc.code)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """统一处理 FastAPI/Starlette 抛出的 HTTPException。

    Args:
        request: 当前请求对象。
        exc: 抛出的 StarletteHTTPException 实例。

    Returns:
        包含 HTTP 错误信封的 JSONResponse。
    """
    detail = exc.detail
    if isinstance(detail, str):
        msg = detail
    else:
        msg = str(detail)
    return _error_response(exc.status_code, msg)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """统一处理请求参数校验失败异常。

    Args:
        request: 当前请求对象。
        exc: 抛出的 RequestValidationError 实例。

    Returns:
        状态码为 422 的错误信封 JSONResponse。
    """
    return _error_response(422, "Invalid request parameters")


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理器，避免未处理异常直接暴露内部细节。

    Args:
        request: 当前请求对象。
        exc: 抛出的未捕获异常实例。

    Returns:
        状态码为 500 的错误信封 JSONResponse，向客户端隐藏具体异常信息。
    """
    logger.exception("Unhandled exception: %s", exc)
    return _error_response(500, "Internal server error")
