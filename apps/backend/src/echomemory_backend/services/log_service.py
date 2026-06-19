"""系统日志业务服务模块，提供日志列表查询与单条详情。"""

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.exceptions.codes import ErrorCode
from echomemory_backend.models.system_log import SystemLog
from echomemory_backend.schemas.system_log import SystemLogListParams


async def list_logs(db: AsyncSession, params: SystemLogListParams) -> tuple[list[SystemLog], int]:
    """按筛选条件分页查询系统日志。

    Args:
        db: SQLAlchemy 异步 Session。
        params: 查询参数（等级、时间范围、关键词、分页）。

    Returns:
        日志实例列表与总记录数组成的元组。
    """
    where_clause: list = []

    if params.level:
        where_clause.append(SystemLog.level == params.level.upper())
    if params.start_time:
        where_clause.append(SystemLog.created_at >= params.start_time)
    if params.end_time:
        where_clause.append(SystemLog.created_at <= params.end_time)
    if params.q:
        where_clause.append(SystemLog.message.ilike(f"%{params.q}%"))

    count_stmt = select(func.count()).select_from(SystemLog).where(*where_clause)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(SystemLog)
        .where(*where_clause)
        .order_by(desc(SystemLog.created_at))
        .limit(params.limit)
        .offset(params.offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return items, total


async def get_log(db: AsyncSession, log_id: int) -> SystemLog:
    """获取单条系统日志详情。

    Args:
        db: SQLAlchemy 异步 Session。
        log_id: 日志 ID。

    Returns:
        SystemLog 实例。

    Raises:
        BusinessError: 日志不存在时抛出 404。
    """
    log = await db.get(SystemLog, log_id)
    if log is None:
        raise BusinessError("日志不存在", code=ErrorCode.RESOURCE_NOT_FOUND)
    return log
