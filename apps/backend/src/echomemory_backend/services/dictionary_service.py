from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.album import AlbumEmotionTag, AlbumInterestTag
from echomemory_backend.models.dictionary import (
    City,
    EmotionTag,
    Instrument,
    InterestTag,
    Language,
    Style,
)
from echomemory_backend.models.music import (
    Music,
    MusicEmotionTag,
    MusicInstrument,
    MusicInterestTag,
)
from echomemory_backend.models.playlist import PlaylistEmotionTag, PlaylistInterestTag
from echomemory_backend.models.user import User
from echomemory_backend.models.user_tag import UserEmotionTag, UserInterestTag
from echomemory_backend.services.user_service import BusinessError

# 字典类型到 ORM 模型的映射
_MODEL_MAP = {
    "styles": Style,
    "languages": Language,
    "cities": City,
    "instruments": Instrument,
    "emotion_tags": EmotionTag,
    "interest_tags": InterestTag,
}

# 删除前需检查的引用关系
_REF_CHECKS = {
    "styles": [(Music, "style_id", "音乐")],
    "languages": [(Music, "language_id", "音乐")],
    "cities": [(User, "city_id", "用户")],
    "instruments": [(MusicInstrument, "instrument_id", "音乐")],
    "emotion_tags": [
        (MusicEmotionTag, "emotion_tag_id", "音乐"),
        (AlbumEmotionTag, "emotion_tag_id", "专辑"),
        (PlaylistEmotionTag, "emotion_tag_id", "歌单"),
        (UserEmotionTag, "emotion_tag_id", "用户"),
    ],
    "interest_tags": [
        (MusicInterestTag, "interest_tag_id", "音乐"),
        (AlbumInterestTag, "interest_tag_id", "专辑"),
        (PlaylistInterestTag, "interest_tag_id", "歌单"),
        (UserInterestTag, "interest_tag_id", "用户"),
    ],
}


def _get_model(dictionary_type: str):
    """根据字典类型获取对应的 ORM 模型类。

    Args:
        dictionary_type: 字典类型标识，如 "styles"、"languages" 等。

    Returns:
        对应的 SQLAlchemy ORM 模型类。

    Raises:
        BusinessError: 字典类型无效时抛出，状态码 400。
    """
    model = _MODEL_MAP.get(dictionary_type)
    if model is None:
        raise BusinessError(
            f"Unknown dictionary type: {dictionary_type}. "
            f"Supported: {', '.join(_MODEL_MAP.keys())}",
            400,
        )
    return model


async def create_dictionary_item(db: AsyncSession, dictionary_type: str, name: str):
    """创建字典项。

    Raises:
        BusinessError: 字典类型无效或名称已存在时抛出。
    """
    model = _get_model(dictionary_type)
    item = model(name=name)
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError(f"Name already exists in {dictionary_type}", 409)
    await db.refresh(item)
    return item


async def get_dictionary_item_by_id(db: AsyncSession, dictionary_type: str, item_id: int):
    """根据 ID 获取字典项。

    Args:
        db: SQLAlchemy 异步 Session。
        dictionary_type: 字典类型标识。
        item_id: 要查询的字典项主键 ID。

    Returns:
        找到的字典项实例，不存在时返回 None。
    """
    model = _get_model(dictionary_type)
    return await db.get(model, item_id)


async def list_dictionary_items(
    db: AsyncSession,
    dictionary_type: str,
    *,
    limit: int = 100,
    offset: int = 0,
):
    """分页列出字典项，按 name 字母序排列。

    Args:
        db: SQLAlchemy 异步 Session。
        dictionary_type: 字典类型标识。
        limit: 每页返回的最大记录数，默认 100。
        offset: 分页偏移量，默认 0。

    Returns:
        字典项实例列表。
    """
    model = _get_model(dictionary_type)
    stmt = select(model).order_by(model.name).limit(limit).offset(offset)
    return (await db.execute(stmt)).scalars().all()


async def update_dictionary_item(
    db: AsyncSession, dictionary_type: str, item_id: int, name: str
):
    """更新字典项名称。

    Raises:
        BusinessError: 字典项不存在或名称冲突时抛出。
    """
    model = _get_model(dictionary_type)
    item = await db.get(model, item_id)
    if item is None:
        raise BusinessError("Dictionary item not found", 404)

    item.name = name
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError(f"Name already exists in {dictionary_type}", 409)
    await db.refresh(item)
    return item


async def delete_dictionary_item(db: AsyncSession, dictionary_type: str, item_id: int):
    """删除字典项，若存在外键引用则拒绝删除。

    Raises:
        BusinessError: 字典项不存在或被引用时抛出。
    """
    model = _get_model(dictionary_type)
    item = await db.get(model, item_id)
    if item is None:
        raise BusinessError("Dictionary item not found", 404)

    # 检查引用关系
    ref_checks = _REF_CHECKS.get(dictionary_type, [])
    for assoc_model, fk_attr, ref_name in ref_checks:
        stmt = (
            select(assoc_model)
            .where(getattr(assoc_model, fk_attr) == item_id)
            .limit(1)
        )
        if (await db.execute(stmt)).scalar_one_or_none() is not None:
            raise BusinessError(
                f"Cannot delete: this item is referenced by {ref_name}", 409
            )

    await db.delete(item)
    await db.commit()
