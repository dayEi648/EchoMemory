"""AI 对话工作流状态定义。"""

from typing import Annotated, Any, NotRequired

from langgraph.graph.message import MessagesState


def _set_user_id(existing: int | None, new: int | None) -> int | None:
    """user_id reducer：仅在首次设置时写入，后续未提供时保持原值。"""
    return new if new is not None else existing


def _set_read_only(existing: bool | None, new: bool | None) -> bool | None:
    """read_only reducer：仅在首次设置时写入，后续未提供时保持原值。"""
    return new if new is not None else existing


def _merge_metadata(
    existing: dict[str, Any] | None,
    new: dict[str, Any] | None,
) -> dict[str, Any]:
    """metadata reducer：合并字典，兼容初始为 None 的情况。"""
    base = existing if existing is not None else {}
    update = new if new is not None else {}
    return {**base, **update}


class AIConversationState(MessagesState):
    """AI 对话图状态。

    继承自 LangGraph ``MessagesState``，复用官方提供的 ``messages`` reducer。
    ``user_id`` 用于标识当前会话所属用户，供节点与工具调用时进行权限判断或查询用户相关数据。
    ``read_only`` 标识当前会话是否只允许使用只读工具。
    ``metadata`` 预留用于后续工具结果、用户画像等附加信息。
    """

    user_id: Annotated[int | None, _set_user_id]
    read_only: Annotated[bool | None, _set_read_only]
    metadata: NotRequired[Annotated[dict[str, Any], _merge_metadata]]
