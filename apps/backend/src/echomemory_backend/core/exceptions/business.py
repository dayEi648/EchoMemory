"""应用级核心异常类。"""

import warnings

from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus


class BusinessError(Exception):
    """业务规则被违反时抛出。

    Attributes:
        detail: 人类可读的错误信息。
        code: 业务错误码，决定返回给客户端的 ``code`` 字段。
        status_code: 建议的 HTTP 状态码；未指定时从 ``code.http_status`` 获取。

    Note:
        推荐调用方式为 ``BusinessError(detail, code=ErrorCode.XXX)``。
        为兼容历史代码，仍支持 ``BusinessError(detail, 401)`` 与
        ``BusinessError(detail, status_code=401)``；当第二个位置参数为
        100~599 的 HTTP 状态码时会被识别为旧调用，并触发 ``DeprecationWarning``。
        ``ErrorCode.SUCCESS`` 不能作为业务错误码使用。
    """

    def __init__(
        self,
        detail: str,
        code: ErrorCode | int | None = None,
        *,
        status_code: int | None = None,
    ):
        """初始化 BusinessError 异常实例。

        Args:
            detail: 人类可读的错误描述信息。
            code: 业务错误码。若传入整数，会转换为 ``ErrorCode`` 枚举。
                为空时兼容旧调用 ``BusinessError(detail, status_code)``。
            status_code: 显式指定的 HTTP 状态码；为空时从 ``code`` 推导。

        Returns:
            None
        """
        self.detail = detail

        if code is None:
            # 兼容旧调用：BusinessError(detail, 401) 或 BusinessError(detail, status_code=401)
            if status_code is not None:
                warnings.warn(
                    "BusinessError(status_code=...) is deprecated, "
                    "use code=ErrorCode.XXX instead",
                    DeprecationWarning,
                    stacklevel=2,
                )
                self.status_code = status_code
                self.code = ErrorCode.from_status(status_code)
            else:
                self.status_code = HttpStatus.BAD_REQUEST
                self.code = ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS
            super().__init__(detail)
            return

        # 兼容旧调用：BusinessError(detail, 401) 中的 401 是 HTTP 状态码而非业务码
        if isinstance(code, int) and not isinstance(code, ErrorCode):
            if 100 <= code < 600:
                warnings.warn(
                    "BusinessError(detail, status_code) is deprecated, "
                    "use code=ErrorCode.XXX instead",
                    DeprecationWarning,
                    stacklevel=2,
                )
                self.status_code = code
                self.code = ErrorCode.from_status(code)
                super().__init__(detail)
                return
            code = ErrorCode(code)
        if code == ErrorCode.SUCCESS:
            raise ValueError("BusinessError 不能使用 ErrorCode.SUCCESS 作为错误码")
        self.code = code
        self.status_code = status_code if status_code is not None else code.http_status
        super().__init__(detail)
