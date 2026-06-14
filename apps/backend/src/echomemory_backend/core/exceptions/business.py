"""应用级核心异常类。"""


class BusinessError(Exception):
    """业务规则被违反时抛出。

    Attributes:
        detail: 人类可读的错误信息。
        status_code: 建议的 HTTP 状态码。
        code: 可选的业务错误码；未指定时由全局处理器按 status_code 推导。
    """

    def __init__(
        self,
        detail: str,
        status_code: int = 400,
        code: int | None = None,
    ):
        """初始化 BusinessError 异常实例。

        Args:
            detail: 人类可读的错误描述信息。
            status_code: 建议返回的 HTTP 状态码，默认为 400。
            code: 可选的业务错误码；未指定时由全局处理器按 status_code 推导。

        Returns:
            None
        """
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)
