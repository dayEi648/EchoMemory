"""应用级核心异常类。"""


class BusinessError(Exception):
    """业务规则被违反时抛出。

    Attributes:
        detail: 人类可读的错误信息。
        status_code: 建议的 HTTP 状态码。
    """

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)
