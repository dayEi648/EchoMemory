"""数据库分页查询辅助模块。"""

from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


@dataclass
class Page:
    """分页查询结果。

    Attributes:
        items: 当前页数据列表。
        total: 满足筛选条件的总记录数。
    """

    items: list
    total: int


async def paginate(
    db: AsyncSession,
    stmt,
    where_clause: list,
    *,
    limit: int,
    offset: int,
) -> Page:
    """执行分页查询并统计总数。

    Args:
        db: SQLAlchemy 异步 Session。
        stmt: 未附加 limit/offset 的 select 语句，where 与 order_by 已包含。
        where_clause: 与 stmt 一致的筛选条件列表，用于 count 查询。
        limit: 每页最大记录数。
        offset: 分页偏移量。

    Returns:
        含 items 与 total 的 Page 对象。
    """
    items = list(
        (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    )
    total = (
        await db.execute(select(func.count()).where(*where_clause))
    ).scalar_one()
    return Page(items=items, total=total)
