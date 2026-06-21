"""统一 API 响应信封 Schema 与辅助函数。"""

from typing import Any

from echomemory_backend.core.exceptions.codes import ErrorCode

# 成功响应固定业务码
API_SUCCESS_CODE = 0
API_SUCCESS_MSG = "success"


def default_error_code(status_code: int) -> int:
    """根据 HTTP 状态码返回默认业务错误码。

    Args:
        status_code: HTTP 状态码。

    Returns:
        对应的默认业务错误码数值。
    """
    return ErrorCode.from_status(status_code).value


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
    code: ErrorCode | int | None = None,
    status_code: int | None = None,
    data: Any = None,
) -> dict[str, Any]:
    """构造失败响应信封字典。

    Args:
        msg: 错误提示信息。
        code: 业务错误码；为空时根据 ``status_code`` 推导。
        status_code: HTTP 状态码，用于在 ``code`` 为空时推导默认业务错误码。
        data: 可选的附加错误详情。

    Returns:
        包含 code、msg、data 的字典。
    """
    if code is None:
        if status_code is None:
            status_code = ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS.http_status
        resolved_code = default_error_code(status_code)
    elif isinstance(code, ErrorCode):
        resolved_code = code.value
    else:
        resolved_code = int(code)
    return {"code": resolved_code, "msg": msg, "data": data}


def wrap_success_payload(payload: Any) -> dict[str, Any]:
    """将原始业务 JSON 负载包装为成功信封。

    Args:
        payload: 端点返回并已序列化的业务数据。

    Returns:
        成功响应信封字典。
    """
    return ok(payload)
