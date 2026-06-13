"""歌单业务逻辑层。

提供歌单的创建、查询、更新、删除，以及歌曲在歌单中的添加与移除等操作。
"""

from sqlalchemy import delete, desc, exists, func, inspect as sa_inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.music import (
    Music,
    MusicEmotionTag,
    MusicInterestTag,
)
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.core.utils import escape_like
from echomemory_backend.db.pagination import paginate
from echomemory_backend.services.association_helpers import (
    rebuild_tag_association,
    sync_owner_tags_from_musics,
)
from echomemory_backend.services.cache_service import (
    invalidate_dashboard_stats,
    invalidate_music_detail,
    invalidate_playlist_detail,
)
from echomemory_backend.services.dictionary_reference_service import (
    validate_emotion_tags_exist,
    validate_interest_tags_exist,
)

DEFAULT_LIKE_PLAYLIST_TITLE = "我喜欢的音乐"


async def _set_playlist_emotion_tags(
    db: AsyncSession, playlist: Playlist, tag_ids: list[int]
) -> None:
    """设置歌单的情感标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 要设置情感标签的歌单实例。
        tag_ids: 情感标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 某标签不存在时抛出，状态码 404。
    """
    await rebuild_tag_association(
        db,
        owner_id=playlist.id,
        owner_fk="playlist_id",
        tag_ids=tag_ids,
        assoc_model=PlaylistEmotionTag,
        tag_fk="emotion_tag_id",
        validate_fn=validate_emotion_tags_exist,
    )


async def _set_playlist_interest_tags(
    db: AsyncSession, playlist: Playlist, tag_ids: list[int]
) -> None:
    """设置歌单的兴趣标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 要设置兴趣标签的歌单实例。
        tag_ids: 兴趣标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 某标签不存在时抛出，状态码 404。
    """
    await rebuild_tag_association(
        db,
        owner_id=playlist.id,
        owner_fk="playlist_id",
        tag_ids=tag_ids,
        assoc_model=PlaylistInterestTag,
        tag_fk="interest_tag_id",
        validate_fn=validate_interest_tags_exist,
    )


async def _sync_playlist_tags_from_musics(
    db: AsyncSession, playlist_id: int
) -> None:
    """根据歌单内所有歌曲的标签并集，重建歌单的情感标签和兴趣标签。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 歌单主键 ID。
    """
    await sync_owner_tags_from_musics(
        db,
        playlist_id,
        music_join_model=PlaylistMusic,
        owner_fk="playlist_id",
        emotion_assoc_model=PlaylistEmotionTag,
        interest_assoc_model=PlaylistInterestTag,
    )


async def create_default_like_playlist(
    db: AsyncSession, user_id: int, *, commit: bool = True
) -> Playlist:
    """为新用户创建默认的「我喜欢的音乐」私密系统歌单。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键 ID。
        commit: 是否立即提交事务，默认 True。

    Returns:
        创建或已存在的系统喜欢歌单实例。

    Raises:
        BusinessError: 数据库唯一约束冲突时抛出，状态码 409。
    """
    stmt = select(Playlist.id).where(
        Playlist.user_id == user_id,
        Playlist.is_like.is_(True),
    )
    existing_id = (await db.execute(stmt)).scalar_one_or_none()
    if existing_id is not None:
        existing = await db.get(Playlist, existing_id)
        assert existing is not None
        return existing

    playlist = Playlist(
        title=DEFAULT_LIKE_PLAYLIST_TITLE,
        user_id=user_id,
        is_private=True,
        is_like=True,
    )
    db.add(playlist)
    if commit:
        await db.commit()
        await db.refresh(playlist)
    else:
        await db.flush()
    return playlist


async def create_playlist(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    description: str | None = None,
    is_private: bool = False,
    cover_icon_url: str | None = None,
) -> Playlist:
    """创建歌单。

    标签由系统根据歌曲收藏自动计算，不允许手动传入。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 创建者用户 ID。
        title: 歌单标题。
        description: 歌单描述，可选。
        is_private: 是否私密，默认 False。
        cover_icon_url: 封面图标 URL，可选。

    Returns:
        创建的歌单实例。
    """
    playlist = Playlist(
        title=title,
        user_id=user_id,
        description=description,
        is_private=is_private,
        cover_icon_url=cover_icon_url,
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    await invalidate_dashboard_stats()
    return playlist


async def get_playlist_by_id(db: AsyncSession, playlist_id: int) -> Playlist | None:
    """根据 ID 获取歌单详情，加载所有关联关系。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 歌单主键 ID。

    Returns:
        歌单实例；不存在时返回 None。
    """
    stmt = (
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(
            selectinload(Playlist.user),
            selectinload(Playlist.musics).selectinload(PlaylistMusic.music),
            selectinload(Playlist.emotion_tags).selectinload(
                PlaylistEmotionTag.emotion_tag
            ),
            selectinload(Playlist.interest_tags).selectinload(
                PlaylistInterestTag.interest_tag
            ),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _public_playlist_where() -> list:
    """公开歌单筛选条件：非私密且非系统喜欢歌单。"""
    return [Playlist.is_private.is_(False), Playlist.is_like.is_(False)]


async def search_playlists(
    db: AsyncSession,
    *,
    q: str | None = None,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """按标题模糊搜索公开歌单，支持标签筛选。

    Args:
        db: SQLAlchemy 异步 Session。
        q: 搜索关键词，可选。
        emotion_tag_id: 按情绪标签 ID 筛选，可选。
        interest_tag_id: 按兴趣标签 ID 筛选，可选。
        limit: 返回数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 匹配的歌单实例列表, "total": 总记录数}。
    """
    where_clause = [
        *_public_playlist_where(),
        exists().where(PlaylistMusic.playlist_id == Playlist.id),  # 排除空歌单
    ]
    if q:
        where_clause.append(
            Playlist.title.ilike(f"%{escape_like(q)}%", escape="\\")
        )
    if emotion_tag_id is not None:
        where_clause.append(
            exists().where(
                (PlaylistEmotionTag.playlist_id == Playlist.id)
                & (PlaylistEmotionTag.emotion_tag_id == emotion_tag_id)
            )
        )
    if interest_tag_id is not None:
        where_clause.append(
            exists().where(
                (PlaylistInterestTag.playlist_id == Playlist.id)
                & (PlaylistInterestTag.interest_tag_id == interest_tag_id)
            )
        )

    stmt = (
        select(Playlist)
        .where(*where_clause)
        .order_by(desc(Playlist.hot), desc(Playlist.created_at))
        .options(selectinload(Playlist.user))
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


async def list_user_public_playlists(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """查询指定用户的公开歌单列表，按创建时间倒序。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键 ID。
        limit: 返回数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 公开歌单实例列表, "total": 总记录数}。
    """
    where_clause = [Playlist.user_id == user_id, *_public_playlist_where()]
    stmt = (
        select(Playlist)
        .where(*where_clause)
        .order_by(desc(Playlist.created_at))
        .options(selectinload(Playlist.user))
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


async def list_user_playlists(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """查询指定用户的歌单列表，按创建时间倒序。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键 ID。
        limit: 返回数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 歌单实例列表, "total": 总记录数}。
    """
    where_clause = [Playlist.user_id == user_id]
    stmt = (
        select(Playlist)
        .where(*where_clause)
        .order_by(desc(Playlist.is_like), desc(Playlist.created_at))
        .options(selectinload(Playlist.user))
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


async def list_user_playlists_with_music_membership(
    db: AsyncSession,
    user_id: int,
    music_id: int,
) -> dict[str, object]:
    """查询用户歌单列表，并标记指定歌曲是否已在各歌单中。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键 ID。
        music_id: 待查询的歌曲 ID。

    Returns:
        {"items": 含 contains_music 标记的歌单列表, "total": 总记录数}。
    """
    where_clause = [Playlist.user_id == user_id]
    stmt = (
        select(Playlist)
        .where(*where_clause)
        .order_by(desc(Playlist.is_like), desc(Playlist.created_at))
        .options(selectinload(Playlist.user))
    )
    playlists = list((await db.execute(stmt)).scalars().all())

    containing_stmt = (
        select(PlaylistMusic.playlist_id)
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .where(
            Playlist.user_id == user_id,
            PlaylistMusic.music_id == music_id,
        )
    )
    containing_ids = set((await db.execute(containing_stmt)).scalars().all())

    items = [
        {
            "playlist": playlist,
            "contains_music": playlist.id in containing_ids,
        }
        for playlist in playlists
    ]
    return {"items": items, "total": len(items)}


async def update_playlist(
    db: AsyncSession,
    playlist: Playlist,
    *,
    title: str | None = None,
    description: str | None = None,
    is_private: bool | None = None,
) -> Playlist:
    """更新歌单文本字段。

    标签由系统根据歌曲收藏自动计算，不允许手动传入。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 待更新的歌单实例。
        title: 新标题，可选。
        description: 新描述，可选。
        is_private: 新隐私状态，可选。

    Returns:
        更新后的歌单实例。

    Raises:
        BusinessError: 系统喜欢歌单不允许修改标题或公开时抛出，状态码 403。
    """
    if playlist.is_like:
        if title is not None and title != playlist.title:
            raise BusinessError("系统歌单不可修改标题", 403)
        if is_private is not None and not is_private:
            raise BusinessError("系统歌单必须保持私密", 403)

    if title is not None:
        playlist.title = title
    if description is not None:
        playlist.description = description
    if is_private is not None:
        playlist.is_private = is_private

    await db.commit()
    await db.refresh(playlist)
    await invalidate_playlist_detail(playlist.id)
    return playlist


async def delete_playlist(db: AsyncSession, playlist: Playlist) -> None:
    """删除歌单（级联删除关联表记录）。

    collect_count 只增不减，删除歌单时不递减音乐收藏数。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 待删除的歌单实例。

    Returns:
        None。

    Raises:
        BusinessError: 系统喜欢歌单不可删除时抛出，状态码 403。
    """
    if playlist.is_like:
        raise BusinessError("系统歌单不可删除", 403)

    # 若 musics 关系已预加载，显式删除关联条目以避免 ORM 级联冲突
    if "musics" not in sa_inspect(playlist).unloaded:
        for pm in list(playlist.musics):
            await db.delete(pm)

    await db.delete(playlist)
    await db.commit()
    await invalidate_playlist_detail(playlist.id)
    await invalidate_dashboard_stats()


async def add_music_to_playlist(
    db: AsyncSession, playlist_id: int, music_id: int
) -> PlaylistMusic:
    """添加一首音乐到歌单。

    校验音乐存在且已发布；查询当前最大 ordinal 并 +1；拒绝重复添加。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 目标歌单 ID。
        music_id: 要添加的音乐 ID。

    Returns:
        创建的 PlaylistMusic 关联实例。

    Raises:
        BusinessError: 音乐不存在或未发布时抛出 404；音乐已在歌单中时抛出 409。
    """
    music = await db.get(Music, music_id)
    if music is None or not music.is_published:
        raise BusinessError("Music not found", 404)

    existing = await db.get(PlaylistMusic, (playlist_id, music_id))
    if existing is not None:
        raise BusinessError("Music already in playlist", 409)

    stmt = select(func.max(PlaylistMusic.ordinal)).where(
        PlaylistMusic.playlist_id == playlist_id
    )
    max_ordinal = (await db.execute(stmt)).scalar_one_or_none() or 0

    playlist_music = PlaylistMusic(
        playlist_id=playlist_id, music_id=music_id, ordinal=max_ordinal + 1
    )
    db.add(playlist_music)
    await db.flush()
    await _sync_playlist_tags_from_musics(db, playlist_id)
    await db.execute(
        update(Music)
        .where(Music.id == music_id)
        .values(collect_count=Music.collect_count + 1)
    )

    # 自动重新计算歌单创建者的用户标签（与主业务同事务提交）
    from echomemory_backend.services.user_tag_service import recalculate_user_tags

    playlist = await db.get(Playlist, playlist_id)
    if playlist is not None:
        await recalculate_user_tags(db, playlist.user_id, commit=False)

    # 自动重新计算热度
    from echomemory_backend.services.hotness_service import (
        recalculate_music_hot,
        recalculate_playlist_hot,
    )

    await recalculate_music_hot(db, music_id)
    await recalculate_playlist_hot(db, playlist_id)

    await db.commit()
    await db.refresh(playlist_music)
    await invalidate_music_detail(music_id)
    await invalidate_playlist_detail(playlist_id)
    return playlist_music


async def remove_music_from_playlist(
    db: AsyncSession, playlist_id: int, music_id: int
) -> None:
    """从歌单移除一首音乐。

    若关联记录不存在，抛出 BusinessError(404)。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 目标歌单 ID。
        music_id: 要移除的音乐 ID。

    Returns:
        None。

    Raises:
        BusinessError: 关联记录不存在时抛出，状态码 404。
    """
    playlist_music = await db.get(PlaylistMusic, (playlist_id, music_id))
    if playlist_music is None:
        raise BusinessError("Music not found in playlist", 404)

    await db.delete(playlist_music)
    await db.flush()
    await _sync_playlist_tags_from_musics(db, playlist_id)

    # 自动重新计算歌单创建者的用户标签（与主业务同事务提交）
    from echomemory_backend.services.user_tag_service import recalculate_user_tags

    playlist = await db.get(Playlist, playlist_id)
    if playlist is not None:
        await recalculate_user_tags(db, playlist.user_id, commit=False)

    # 自动重新计算歌单热度
    from echomemory_backend.services.hotness_service import recalculate_playlist_hot

    await recalculate_playlist_hot(db, playlist_id)

    await db.commit()
    await invalidate_playlist_detail(playlist_id)
