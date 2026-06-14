"""统一 API 响应信封 Schema 与辅助函数。"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

# 成功响应固定业务码
API_SUCCESS_CODE = 0
API_SUCCESS_MSG = "success"

# HTTP 状态码到默认业务错误码的映射（status * 100 + 1）
_DEFAULT_ERROR_CODE_BY_STATUS: dict[int, int] = {
    400: 40001,
    401: 40101,
    403: 40301,
    404: 40401,
    409: 40901,
    422: 42201,
    429: 42901,
    500: 50001,
    502: 50201,
    503: 50301,
}

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应信封。

    Attributes:
        code: 业务状态码，0 表示成功，非 0 表示失败。
        msg: 人类可读提示信息。
        data: 业务数据；失败时为 null。
    """

    code: int
    msg: str
    data: T | None = None


def default_error_code(status_code: int) -> int:
    """根据 HTTP 状态码返回默认业务错误码。

    Args:
        status_code: HTTP 状态码。

    Returns:
        对应的默认业务错误码；未映射时返回 ``status_code * 100 + 1``。
    """
    return _DEFAULT_ERROR_CODE_BY_STATUS.get(status_code, status_code * 100 + 1)


def is_envelope(payload: Any) -> bool:
    """判断 JSON 负载是否已是统一响应信封。

    Args:
        payload: 解析后的 JSON 对象。

    Returns:
        同时包含 ``code`` 与 ``msg`` 字段时返回 True。
    """
    return isinstance(payload, dict) and "code" in payload and "msg" in payload


def ok(data: Any = None, msg: str = API_SUCCESS_MSG) -> dict[str, Any]:
    """构造成功响应信封字典。

    Args:
        data: 业务数据，无数据时为 None。
        msg: 成功提示信息。

    Returns:
        包含 code、msg、data 的字典。
    """
    return {"code": API_SUCCESS_CODE, "msg": msg, "data": data}


def error_body(
    msg: str,
    *,
    status_code: int = 400,
    code: int | None = None,
    data: Any = None,
) -> dict[str, Any]:
    """构造失败响应信封字典。

    Args:
        msg: 错误提示信息。
        status_code: HTTP 状态码，用于推导默认业务错误码。
        code: 可选的自定义业务错误码。
        data: 可选的附加错误详情。

    Returns:
        包含 code、msg、data 的字典。
    """
    resolved_code = code if code is not None else default_error_code(status_code)
    return {"code": resolved_code, "msg": msg, "data": data}


def wrap_success_payload(payload: Any) -> dict[str, Any]:
    """将原始业务 JSON 负载包装为成功信封。

    Args:
        payload: 端点返回并已序列化的业务数据。

    Returns:
        成功响应信封字典。
    """
    return ok(payload)
