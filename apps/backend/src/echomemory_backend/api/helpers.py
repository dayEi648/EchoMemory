"""API 层通用辅助函数。"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException, status
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return entity


async def build_detail_response(
    entity,
    schema_cls: type,
    check_fn: Callable[..., Awaitable[bool]],
    db: AsyncSession,
    current_user,
    *,
    entity_id: int | None = None,
    field_name: str = "is_collected_by_me",
):
    """构造带收藏状态的详情响应 Schema。

    Args:
        entity: ORM 实体实例。
        schema_cls: 输出 Pydantic Schema 类。
        check_fn: 异步收藏状态检查函数，签名为 (db, user_id, entity_id) -> bool。
        db: SQLAlchemy 异步 Session。
        current_user: 当前用户实例，None 时收藏状态为 False。
        entity_id: 实体主键，默认取 entity.id。
        field_name: 收藏状态字段名，默认 is_collected_by_me。

    Returns:
        填充了收藏状态的 Schema 实例。
    """
    resolved_id = entity_id if entity_id is not None else entity.id
    collected = False
    if current_user is not None:
        collected = await check_fn(db, current_user.id, resolved_id)
    return schema_cls.model_validate(entity).model_copy(
        update={field_name: collected}
    )
