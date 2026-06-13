"""全局异常处理器。

提供应用级别的统一异常处理，将业务异常、HTTP 异常、参数校验异常以及未捕获异常
统一转换为 JSON 响应，避免内部细节泄露给客户端。
"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from echomemory_backend.core.exceptions.business import BusinessError

logger = logging.getLogger(__name__)


async def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    """将业务异常统一转换为 JSON 响应，确保前端能感知具体错误信息。

    Args:
        request: 当前请求对象。
        exc: 抛出的 BusinessError 实例。

    Returns:
        包含业务错误详情的 JSONResponse。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """统一处理 FastAPI/Starlette 抛出的 HTTPException。

    Args:
        request: 当前请求对象。
        exc: 抛出的 StarletteHTTPException 实例。

    Returns:
        包含 HTTP 错误详情的 JSONResponse。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """统一处理请求参数校验失败异常。

    Args:
        request: 当前请求对象。
        exc: 抛出的 RequestValidationError 实例。

    Returns:
        状态码为 422 的 JSONResponse。
    """
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request parameters"},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理器，避免未处理异常直接暴露内部细节。

    Args:
        request: 当前请求对象。
        exc: 抛出的未捕获异常实例。

    Returns:
        状态码为 500 的 JSONResponse，向客户端隐藏具体异常信息。
    """
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
