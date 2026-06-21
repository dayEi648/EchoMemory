"""API 层通用辅助函数。"""
from echomemory_backend.core.exceptions.codes import HttpStatus

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def require_entity(
    getter: Callable[..., Awaitable[T | None]],
    db: AsyncSession,
    entity_id: int,
    *,
    detail: str = "Resource not found",
    predicate: Callable[[T], bool] | None = None,
) -> T:
    """获取实体，不存在或不满足 predicate 时抛出 404。

    Args:
        getter: 异步查询函数，签名为 (db, entity_id) -> T | None。
        db: SQLAlchemy 异步 Session。
        entity_id: 实体主键。
        detail: 404 响应 detail 文案。
        predicate: 可选的额外校验函数，返回 False 时视为不存在。

    Returns:
        查询到的实体实例。

    Raises:
        HTTPException: 实体不存在或未通过 predicate 时抛出 404。
    """
    entity = await getter(db, entity_id)
    if entity is None or (predicate is not None and not predicate(entity)):
        raise HTTPException(status_code=HttpStatus.NOT_FOUND, detail=detail)
    return entity


async def build_detail_response_from_schema(
    schema_obj,
    check_fn: Callable[..., Awaitable[bool]],
    db: AsyncSession,
    current_user,
    *,
    entity_id: int | None = None,
    field_name: str = "is_collected_by_me",
):
    """从已构建的 Schema 实例中填充当前用户状态。

    用于缓存场景：公共详情已从缓存取出，只需合并当前用户的收藏/关注状态。

    Args:
        schema_obj: 已构建的 Pydantic Schema 实例（不含用户状态）。
        check_fn: 异步状态检查函数，签名为 (db, user_id, entity_id) -> bool。
        db: SQLAlchemy 异步 Session。
        current_user: 当前用户实例，None 时状态为 False。
        entity_id: 实体主键，默认取 schema_obj.id。
        field_name: 状态字段名，默认 is_collected_by_me。

    Returns:
        填充了用户状态的 Schema 实例。
    """
    resolved_id = entity_id if entity_id is not None else schema_obj.id
    collected = False
    if current_user is not None:
        collected = await check_fn(db, current_user.id, resolved_id)
    return schema_obj.model_copy(update={field_name: collected})
