"""测试用 API 响应信封解析辅助函数。"""

from typing import Any

from httpx import Response


def api_body(response: Response) -> dict[str, Any]:
    """解析响应 JSON 为字典。

    Args:
        response: HTTP 响应对象。

    Returns:
        解析后的 JSON 字典。
    """
    return response.json()


def api_data(response: Response) -> Any:
    """从成功响应信封中取出 ``data`` 字段。

    Args:
        response: HTTP 响应对象。

    Returns:
        业务数据负载。

    Raises:
        AssertionError: 当 ``code`` 不为 0 时抛出。
    """
    body = api_body(response)
    assert body.get("code") == 0, body
    return body.get("data")


def api_error(response: Response) -> dict[str, Any]:
    """解析失败响应信封。

    Args:
        response: HTTP 响应对象。

    Returns:
        完整错误信封字典。

    Raises:
        AssertionError: 当 ``code`` 为 0 时抛出。
    """
    body = api_body(response)
    assert body.get("code") != 0, body
    return body


def api_msg(response: Response) -> str:
    """从响应信封中取出 ``msg`` 字段。

    Args:
        response: HTTP 响应对象。

    Returns:
        提示信息字符串。
    """
    return api_body(response).get("msg", "")
