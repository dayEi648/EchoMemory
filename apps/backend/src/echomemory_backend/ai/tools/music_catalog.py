"""面向 AI 的音乐、歌单、专辑目录与用户动作工具。"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from pydantic import Field
from sqlalchemy import desc, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.ai.tools.confirmation import (
    ConfirmationAction,
    ConfirmationResourceType,
    create_confirmation_token,
    decode_confirmation_token,
    release_confirmation,
    reserve_confirmation,
)
from echomemory_backend.db.session import AsyncSessionLocal
from echomemory_backend.models.album import (
    Album,
    AlbumAuthor,
    AlbumEmotionTag,
    AlbumInterestTag,
    AlbumMusic,
)
from echomemory_backend.models.dictionary import (
    EmotionTag,
    Instrument,
    InterestTag,
    Language,
    Style,
)
from echomemory_backend.models.music import (
    Music,
    MusicAuthor,
    MusicEmotionTag,
    MusicInstrument,
    MusicInterestTag,
)
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.models.user import User
from echomemory_backend.models.user_profile import UserProfile
from echomemory_backend.models.user_tag import (
    UserEmotionTag,
    UserInterestTag,
    UserLanguage,
    UserStyle,
)
from echomemory_backend.services import collection_service, playlist_service
from echomemory_backend.core.utils.common import escape_like

MatchMode = Literal["exact", "fuzzy"]
CatalogSort = Literal["relevance", "hot", "play_count", "newest"]
ResultLimit = Annotated[int, Field(ge=1, le=20)]
PositiveResourceId = Annotated[int, Field(ge=1)]
ResourceIds = Annotated[list[PositiveResourceId], Field(min_length=1, max_length=10)]

_PUBLIC_ARTIFACT_VERSION = 1


def _runtime_user_id(runtime: ToolRuntime) -> int:
    """从不可由模型控制的运行时 state 读取当前用户 ID。"""
    user_id = runtime.state.get("user_id")
    if not isinstance(user_id, int) or user_id < 1:
        raise RuntimeError("AI tool runtime has no authenticated user")
    return user_id


def _ordered(items: list, ids: list[int]) -> list:
    """按调用方给出的 ID 顺序排列 ORM 对象。"""
    positions = {resource_id: index for index, resource_id in enumerate(ids)}
    return sorted(items, key=lambda item: positions[item.id])


def _names(associations: list, attribute: str) -> list[str]:
    """从关联对象中提取名称并稳定排序。"""
    values = [getattr(getattr(item, attribute), "name") for item in associations]
    return sorted(set(values))


def _music_authors(music: Music) -> list[str]:
    return [
        association.author.nickname
        for association in sorted(music.authors, key=lambda item: item.ordinal)
    ]


def _album_authors(album: Album) -> list[str]:
    return [
        association.author.nickname
        for association in sorted(album.authors, key=lambda item: item.ordinal)
    ]


def _music_album(music: Music) -> str | None:
    for association in music.album_musics:
        if not association.album.is_deleted:
            return association.album.title
    return None


def _contains(column, value: str):
    """构造转义通配符后的大小写不敏感包含条件。"""
    return column.ilike(f"%{escape_like(value)}%", escape="\\")


def _music_for_model(music: Music) -> dict[str, object]:
    """生成只包含模型检索与决策所需字段的音乐数据。"""
    return {
        "id": music.id,
        "title": music.title,
        "authors": _music_authors(music),
        "album": _music_album(music),
        "style": music.style.name if music.style else None,
        "language": music.language.name if music.language else None,
        "emotion_tags": _names(music.emotion_tags, "emotion_tag"),
        "interest_tags": _names(music.interest_tags, "interest_tag"),
        "instruments": _names(music.instruments, "instrument"),
        "is_vip": music.is_vip,
        "release_date": music.release_date.isoformat() if music.release_date else None,
        "hot": music.hot,
    }


def _music_load_options() -> tuple:
    return (
        selectinload(Music.style),
        selectinload(Music.language),
        selectinload(Music.authors).selectinload(MusicAuthor.author),
        selectinload(Music.instruments).selectinload(MusicInstrument.instrument),
        selectinload(Music.emotion_tags).selectinload(MusicEmotionTag.emotion_tag),
        selectinload(Music.interest_tags).selectinload(MusicInterestTag.interest_tag),
        selectinload(Music.album_musics).selectinload(AlbumMusic.album),
    )


@tool
async def search_music_catalog(
    title: str | None = None,
    match_mode: MatchMode = "fuzzy",
    author: str | None = None,
    album: str | None = None,
    styles: list[str] | None = None,
    languages: list[str] | None = None,
    instruments: list[str] | None = None,
    emotion_tags: list[str] | None = None,
    interest_tags: list[str] | None = None,
    is_vip: bool | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    sort_by: CatalogSort = "relevance",
    limit: ResultLimit = 10,
) -> dict[str, object]:
    """查询已上架音乐，支持精确/模糊标题和多维筛选。

    当用户要找歌曲、按歌手/专辑/风格/语言/乐器/情绪/兴趣/VIP/发行日期筛选，
    或个性推荐流程需要候选音乐时使用。返回的 ID 只用于后续工具调用，
    严禁在自然语言回复中向用户展示或复述 ID。筛选列表按“匹配其中任意一个”处理。

    Args:
        title: 歌曲标题；省略时不按标题筛选。
        match_mode: 标题匹配方式，``"exact"`` 为精确匹配，``"fuzzy"`` 为模糊包含。
        author: 歌手昵称或用户名关键词。
        album: 所属专辑标题关键词。
        styles: 曲风名称列表，匹配其中任意一个。
        languages: 语言名称列表，匹配其中任意一个。
        instruments: 乐器名称列表，匹配其中任意一个。
        emotion_tags: 情绪标签名称列表，匹配其中任意一个。
        interest_tags: 兴趣标签名称列表，匹配其中任意一个。
        is_vip: 是否 VIP 曲目；省略时不按 VIP 状态筛选。
        release_date_from: 发行日期下限（含）。
        release_date_to: 发行日期上限（含）。
        sort_by: 排序字段，可选 ``"relevance"``、``"hot"``、``"play_count"``、``"newest"``。
        limit: 返回条数上限，范围 1 到 20。

    Returns:
        包含 ``items`` 与 ``total`` 的字典。``items`` 为音乐对象列表，每项含
        ``id``、``title``、``authors``、``album``、``style``、``language``、
        ``emotion_tags``、``interest_tags``、``instruments``、``is_vip``、
        ``release_date``、``hot``；``total`` 为符合条件的总条数。
    """
    where_clause = [Music.is_published.is_(True)]
    normalized_title = title.strip() if title else None
    if normalized_title:
        if match_mode == "exact":
            where_clause.append(func.lower(Music.title) == normalized_title.lower())
        else:
            where_clause.append(_contains(Music.title, normalized_title))
    if author and author.strip():
        keyword = author.strip()
        where_clause.append(
            exists()
            .where(MusicAuthor.music_id == Music.id)
            .where(MusicAuthor.author_id == User.id)
            .where(
                or_(
                    _contains(User.nickname, keyword),
                    _contains(User.username, keyword),
                )
            )
        )
    if album and album.strip():
        keyword = album.strip()
        where_clause.append(
            exists()
            .where(AlbumMusic.music_id == Music.id)
            .where(AlbumMusic.album_id == Album.id)
            .where(Album.is_deleted.is_(False))
            .where(_contains(Album.title, keyword))
        )
    if styles:
        where_clause.append(
            exists()
            .where(Style.id == Music.style_id)
            .where(Style.name.in_(styles))
        )
    if languages:
        where_clause.append(
            exists()
            .where(Language.id == Music.language_id)
            .where(Language.name.in_(languages))
        )
    if instruments:
        where_clause.append(
            exists()
            .where(MusicInstrument.music_id == Music.id)
            .where(MusicInstrument.instrument_id == Instrument.id)
            .where(Instrument.name.in_(instruments))
        )
    if emotion_tags:
        where_clause.append(
            exists()
            .where(MusicEmotionTag.music_id == Music.id)
            .where(MusicEmotionTag.emotion_tag_id == EmotionTag.id)
            .where(EmotionTag.name.in_(emotion_tags))
        )
    if interest_tags:
        where_clause.append(
            exists()
            .where(MusicInterestTag.music_id == Music.id)
            .where(MusicInterestTag.interest_tag_id == InterestTag.id)
            .where(InterestTag.name.in_(interest_tags))
        )
    if is_vip is not None:
        where_clause.append(Music.is_vip.is_(is_vip))
    if release_date_from is not None:
        where_clause.append(Music.release_date >= release_date_from)
    if release_date_to is not None:
        where_clause.append(Music.release_date <= release_date_to)

    order_by = {
        "hot": (desc(Music.hot), desc(Music.id)),
        "play_count": (desc(Music.play_count), desc(Music.id)),
        "newest": (desc(Music.release_date), desc(Music.id)),
        "relevance": (desc(Music.hot), desc(Music.id)),
    }[sort_by]
    async with AsyncSessionLocal() as db:
        total = (
            await db.execute(
                select(func.count(Music.id)).where(*where_clause)
            )
        ).scalar_one()
        rows = await db.execute(
            select(Music)
            .where(*where_clause)
            .order_by(*order_by)
            .limit(limit)
            .options(*_music_load_options())
        )
        items = [_music_for_model(music) for music in rows.scalars().all()]
    return {"items": items, "total": total}


@tool
async def search_playlist_catalog(
    title: str | None = None,
    match_mode: MatchMode = "fuzzy",
    creator: str | None = None,
    emotion_tags: list[str] | None = None,
    interest_tags: list[str] | None = None,
    sort_by: CatalogSort = "relevance",
    limit: ResultLimit = 10,
) -> dict[str, object]:
    """查询公开、非系统喜欢且非空的歌单。

    支持精确/模糊标题、创建者、情绪标签、兴趣标签和排序筛选。
    返回的 ID 只用于后续推送或收藏工具，严禁在自然语言回复中透露。

    Args:
        title: 歌单标题；省略时不按标题筛选。
        match_mode: 标题匹配方式，``"exact"`` 为精确匹配，``"fuzzy"`` 为模糊包含。
        creator: 创建者昵称或用户名关键词。
        emotion_tags: 情绪标签名称列表，匹配其中任意一个。
        interest_tags: 兴趣标签名称列表，匹配其中任意一个。
        sort_by: 排序字段，可选 ``"relevance"``、``"hot"``、``"play_count"``、``"newest"``。
        limit: 返回条数上限，范围 1 到 20。

    Returns:
        包含 ``items`` 与 ``total`` 的字典。``items`` 为歌单对象列表，每项含
        ``id``、``title``、``creator``、``description``、``emotion_tags``、
        ``interest_tags``、``music_count``、``hot``；``total`` 为符合条件的总条数。
    """
    where_clause = [
        Playlist.is_private.is_(False),
        Playlist.is_like.is_(False),
        exists().where(PlaylistMusic.playlist_id == Playlist.id),
    ]
    normalized_title = title.strip() if title else None
    if normalized_title:
        if match_mode == "exact":
            where_clause.append(func.lower(Playlist.title) == normalized_title.lower())
        else:
            where_clause.append(_contains(Playlist.title, normalized_title))
    if creator and creator.strip():
        keyword = creator.strip()
        where_clause.extend(
            [
                Playlist.user_id == User.id,
                or_(
                    _contains(User.nickname, keyword),
                    _contains(User.username, keyword),
                ),
            ]
        )
    if emotion_tags:
        where_clause.append(
            exists()
            .where(PlaylistEmotionTag.playlist_id == Playlist.id)
            .where(PlaylistEmotionTag.emotion_tag_id == EmotionTag.id)
            .where(EmotionTag.name.in_(emotion_tags))
        )
    if interest_tags:
        where_clause.append(
            exists()
            .where(PlaylistInterestTag.playlist_id == Playlist.id)
            .where(PlaylistInterestTag.interest_tag_id == InterestTag.id)
            .where(InterestTag.name.in_(interest_tags))
        )
    order_by = {
        "hot": (desc(Playlist.hot), desc(Playlist.id)),
        "play_count": (desc(Playlist.play_count), desc(Playlist.id)),
        "newest": (desc(Playlist.created_at), desc(Playlist.id)),
        "relevance": (desc(Playlist.hot), desc(Playlist.id)),
    }[sort_by]
    async with AsyncSessionLocal() as db:
        count_stmt = select(func.count(Playlist.id))
        stmt = select(Playlist)
        if creator and creator.strip():
            count_stmt = count_stmt.select_from(Playlist).join(User, Playlist.user_id == User.id)
            stmt = stmt.join(User, Playlist.user_id == User.id)
        total = (await db.execute(count_stmt.where(*where_clause))).scalar_one()
        rows = await db.execute(
            stmt.where(*where_clause)
            .order_by(*order_by)
            .limit(limit)
            .options(
                selectinload(Playlist.user),
                selectinload(Playlist.musics),
                selectinload(Playlist.emotion_tags).selectinload(
                    PlaylistEmotionTag.emotion_tag
                ),
                selectinload(Playlist.interest_tags).selectinload(
                    PlaylistInterestTag.interest_tag
                ),
            )
        )
        items = [
            {
                "id": playlist.id,
                "title": playlist.title,
                "creator": playlist.user.nickname,
                "description": playlist.description,
                "emotion_tags": _names(playlist.emotion_tags, "emotion_tag"),
                "interest_tags": _names(playlist.interest_tags, "interest_tag"),
                "music_count": len(playlist.musics),
                "hot": playlist.hot,
            }
            for playlist in rows.scalars().unique().all()
        ]
    return {"items": items, "total": total}


@tool
async def search_album_catalog(
    title: str | None = None,
    match_mode: MatchMode = "fuzzy",
    author: str | None = None,
    emotion_tags: list[str] | None = None,
    interest_tags: list[str] | None = None,
    sort_by: CatalogSort = "relevance",
    limit: ResultLimit = 10,
) -> dict[str, object]:
    """查询未删除且包含已上架音乐的专辑。

    支持精确/模糊标题、作者、情绪标签、兴趣标签和排序筛选。
    返回的 ID 只用于后续推送或收藏工具，严禁在自然语言回复中透露。

    Args:
        title: 专辑标题；省略时不按标题筛选。
        match_mode: 标题匹配方式，``"exact"`` 为精确匹配，``"fuzzy"`` 为模糊包含。
        author: 作者昵称或用户名关键词。
        emotion_tags: 情绪标签名称列表，匹配其中任意一个。
        interest_tags: 兴趣标签名称列表，匹配其中任意一个。
        sort_by: 排序字段，可选 ``"relevance"``、``"hot"``、``"play_count"``、``"newest"``。
        limit: 返回条数上限，范围 1 到 20。

    Returns:
        包含 ``items`` 与 ``total`` 的字典。``items`` 为专辑对象列表，每项含
        ``id``、``title``、``authors``、``description``、``emotion_tags``、
        ``interest_tags``、``music_count``、``hot``；``total`` 为符合条件的总条数。
    """
    published_music_exists = (
        exists()
        .where(AlbumMusic.album_id == Album.id)
        .where(AlbumMusic.music_id == Music.id)
        .where(Music.is_published.is_(True))
    )
    where_clause = [Album.is_deleted.is_(False), published_music_exists]
    normalized_title = title.strip() if title else None
    if normalized_title:
        if match_mode == "exact":
            where_clause.append(func.lower(Album.title) == normalized_title.lower())
        else:
            where_clause.append(_contains(Album.title, normalized_title))
    if author and author.strip():
        keyword = author.strip()
        where_clause.append(
            exists()
            .where(AlbumAuthor.album_id == Album.id)
            .where(AlbumAuthor.author_id == User.id)
            .where(
                or_(
                    _contains(User.nickname, keyword),
                    _contains(User.username, keyword),
                )
            )
        )
    if emotion_tags:
        where_clause.append(
            exists()
            .where(AlbumEmotionTag.album_id == Album.id)
            .where(AlbumEmotionTag.emotion_tag_id == EmotionTag.id)
            .where(EmotionTag.name.in_(emotion_tags))
        )
    if interest_tags:
        where_clause.append(
            exists()
            .where(AlbumInterestTag.album_id == Album.id)
            .where(AlbumInterestTag.interest_tag_id == InterestTag.id)
            .where(InterestTag.name.in_(interest_tags))
        )
    order_by = {
        "hot": (desc(Album.hot), desc(Album.id)),
        "play_count": (desc(Album.play_count), desc(Album.id)),
        "newest": (desc(Album.created_at), desc(Album.id)),
        "relevance": (desc(Album.hot), desc(Album.id)),
    }[sort_by]
    async with AsyncSessionLocal() as db:
        total = (
            await db.execute(select(func.count(Album.id)).where(*where_clause))
        ).scalar_one()
        rows = await db.execute(
            select(Album)
            .where(*where_clause)
            .order_by(*order_by)
            .limit(limit)
            .options(
                selectinload(Album.authors).selectinload(AlbumAuthor.author),
                selectinload(Album.musics).selectinload(AlbumMusic.music),
                selectinload(Album.emotion_tags).selectinload(
                    AlbumEmotionTag.emotion_tag
                ),
                selectinload(Album.interest_tags).selectinload(
                    AlbumInterestTag.interest_tag
                ),
            )
        )
        albums = rows.scalars().all()
        items = [
            {
                "id": album_item.id,
                "title": album_item.title,
                "authors": _album_authors(album_item),
                "description": album_item.description,
                "emotion_tags": _names(album_item.emotion_tags, "emotion_tag"),
                "interest_tags": _names(album_item.interest_tags, "interest_tag"),
                "music_count": sum(
                    1 for association in album_item.musics if association.music.is_published
                ),
                "hot": album_item.hot,
            }
            for album_item in albums
        ]
    return {"items": items, "total": total}


def _tool_message(
    runtime: ToolRuntime,
    *,
    content: str,
    artifact: dict[str, object],
) -> ToolMessage:
    """创建会持久化进 checkpoint 的结构化工具消息。"""
    return ToolMessage(
        content=content,
        artifact=artifact,
        tool_call_id=runtime.tool_call_id or "",
    )


@tool
async def push_music_cards(
    resource_ids: ResourceIds,
    runtime: ToolRuntime,
) -> ToolMessage:
    """把已查询到的已上架音乐作为音乐卡片推送给用户。

    卡片支持进入音乐详情和直接播放。只能传入查询工具刚返回的音乐 ID，
    不要猜测 ID；不要在自然语言回复中展示 ID。一次最多推送 10 首。

    Args:
        resource_ids: 音乐 ID 列表，长度 1 到 10，须来自 ``search_music_catalog`` 的返回结果。

    Returns:
        结构化 ``ToolMessage``。``content`` 为推送摘要文本；``artifact`` 含
        ``type``（``"music_card"``）、``version`` 及 ``items`` 列表，每项含
        ``id``、``title``、``authors``、``album``、``cover_url``、``is_vip``。
    """
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Music)
            .where(Music.id.in_(resource_ids), Music.is_published.is_(True))
            .options(*_music_load_options())
        )
        musics = _ordered(list(rows.scalars().all()), resource_ids)
    items = [
        {
            "id": music.id,
            "title": music.title,
            "authors": _music_authors(music),
            "album": _music_album(music),
            "cover_url": music.cover_icon_url,
            "is_vip": music.is_vip,
        }
        for music in musics
    ]
    return _tool_message(
        runtime,
        content=f"已向用户推送 {len(items)} 首音乐。",
        artifact={"version": _PUBLIC_ARTIFACT_VERSION, "type": "music_card", "items": items},
    )


@tool
async def push_playlist_cards(
    resource_ids: ResourceIds,
    runtime: ToolRuntime,
) -> ToolMessage:
    """把已查询到的公开歌单作为歌单卡片推送给用户。

    卡片用于进入歌单详情。只能传入查询工具刚返回的歌单 ID，不要猜测 ID；
    不要在自然语言回复中展示 ID。一次最多推送 10 个。

    Args:
        resource_ids: 歌单 ID 列表，长度 1 到 10，须来自 ``search_playlist_catalog`` 的返回结果。

    Returns:
        结构化 ``ToolMessage``。``content`` 为推送摘要文本；``artifact`` 含
        ``type``（``"playlist_card"``）、``version`` 及 ``items`` 列表，每项含
        ``id``、``title``、``creator``、``description``、``cover_url``、``music_count``。
    """
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Playlist)
            .where(
                Playlist.id.in_(resource_ids),
                Playlist.is_private.is_(False),
                Playlist.is_like.is_(False),
                exists().where(PlaylistMusic.playlist_id == Playlist.id),
            )
            .options(selectinload(Playlist.user), selectinload(Playlist.musics))
        )
        playlists = _ordered(list(rows.scalars().all()), resource_ids)
    items = [
        {
            "id": playlist.id,
            "title": playlist.title,
            "creator": playlist.user.nickname,
            "description": playlist.description,
            "cover_url": playlist.cover_icon_url,
            "music_count": len(playlist.musics),
        }
        for playlist in playlists
    ]
    return _tool_message(
        runtime,
        content=f"已向用户推送 {len(items)} 个歌单。",
        artifact={
            "version": _PUBLIC_ARTIFACT_VERSION,
            "type": "playlist_card",
            "items": items,
        },
    )


@tool
async def push_album_cards(
    resource_ids: ResourceIds,
    runtime: ToolRuntime,
) -> ToolMessage:
    """把已查询到的可见专辑作为专辑卡片推送给用户。

    卡片用于进入专辑详情。只能传入查询工具刚返回的专辑 ID，不要猜测 ID；
    不要在自然语言回复中展示 ID。一次最多推送 10 个。

    Args:
        resource_ids: 专辑 ID 列表，长度 1 到 10，须来自 ``search_album_catalog`` 的返回结果。

    Returns:
        结构化 ``ToolMessage``。``content`` 为推送摘要文本；``artifact`` 含
        ``type``（``"album_card"``）、``version`` 及 ``items`` 列表，每项含
        ``id``、``title``、``authors``、``description``、``cover_url``、``music_count``。
    """
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Album)
            .where(
                Album.id.in_(resource_ids),
                Album.is_deleted.is_(False),
                exists()
                .where(AlbumMusic.album_id == Album.id)
                .where(AlbumMusic.music_id == Music.id)
                .where(Music.is_published.is_(True)),
            )
            .options(
                selectinload(Album.authors).selectinload(AlbumAuthor.author),
                selectinload(Album.musics).selectinload(AlbumMusic.music),
            )
        )
        albums = _ordered(list(rows.scalars().all()), resource_ids)
    items = [
        {
            "id": album.id,
            "title": album.title,
            "authors": _album_authors(album),
            "description": album.description,
            "cover_url": album.cover_icon_url or album.cover_url,
            "music_count": sum(
                1 for association in album.musics if association.music.is_published
            ),
        }
        for album in albums
    ]
    return _tool_message(
        runtime,
        content=f"已向用户推送 {len(items)} 个专辑。",
        artifact={"version": _PUBLIC_ARTIFACT_VERSION, "type": "album_card", "items": items},
    )


async def _load_confirmation_resource(
    db: AsyncSession,
    *,
    resource_type: ConfirmationResourceType,
    resource_id: int,
    user_id: int,
) -> tuple[str, str | None]:
    """校验资源可见性并返回标题与封面。"""
    if resource_type == "music":
        resource = await db.get(Music, resource_id)
        if resource is None or not resource.is_published:
            raise ValueError("音乐不存在或尚未上架")
        return resource.title, resource.cover_icon_url
    if resource_type == "playlist":
        resource = await db.get(Playlist, resource_id)
        has_music = (
            await db.execute(
                select(
                    exists().where(PlaylistMusic.playlist_id == resource_id)
                )
            )
        ).scalar_one()
        if (
            resource is None
            or resource.is_private
            or resource.is_like
            or resource.user_id == user_id
            or not has_music
        ):
            raise ValueError("歌单不存在或不可收藏")
        return resource.title, resource.cover_icon_url
    resource = await db.get(Album, resource_id)
    has_published_music = (
        await db.execute(
            select(
                exists()
                .where(AlbumMusic.album_id == resource_id)
                .where(AlbumMusic.music_id == Music.id)
                .where(Music.is_published.is_(True))
            )
        )
    ).scalar_one()
    if resource is None or resource.is_deleted or not has_published_music:
        raise ValueError("专辑不存在")
    return resource.title, resource.cover_icon_url or resource.cover_url


async def _request_collection_change(
    *,
    resource_type: ConfirmationResourceType,
    resource_id: int,
    action: ConfirmationAction,
    runtime: ToolRuntime,
) -> ToolMessage:
    user_id = _runtime_user_id(runtime)
    async with AsyncSessionLocal() as db:
        title, cover_url = await _load_confirmation_resource(
            db,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
        )
    token = create_confirmation_token(
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
    )
    action_label = "收藏" if action == "collect" else "取消收藏"
    resource_label = {"music": "音乐", "playlist": "歌单", "album": "专辑"}[
        resource_type
    ]
    artifact = {
        "version": _PUBLIC_ARTIFACT_VERSION,
        "type": "confirmation_card",
        "resource_type": resource_type,
        "action": action,
        "resource": {
            "id": resource_id,
            "title": title,
            "cover_url": cover_url,
        },
        "confirmation_token": token,
        "prompt": f"确认{action_label}{resource_label}《{title}》吗？",
    }
    return _tool_message(
        runtime,
        content=f"已请求用户确认{action_label}{resource_label}《{title}》，等待用户操作。",
        artifact=artifact,
    )


@tool
async def request_music_collection_change(
    resource_id: PositiveResourceId,
    action: ConfirmationAction,
    runtime: ToolRuntime,
) -> ToolMessage:
    """请求用户二次确认收藏或取消收藏一首已上架音乐。

    用户表达收藏意图后先调用本工具，绝不能直接执行写操作。ID 必须来自查询结果。
    本工具只生成确认卡片，不会修改收藏状态。

    Args:
        resource_id: 音乐 ID，须来自 ``search_music_catalog`` 的返回结果。
        action: 操作类型，``"collect"`` 为收藏，``"uncollect"`` 为取消收藏。

    Returns:
        结构化 ``ToolMessage``。``content`` 为等待确认的摘要文本；``artifact`` 含
        ``type``（``"confirmation_card"``）、``resource_type``、``action``、
        ``resource``（``id``、``title``、``cover_url``）、``confirmation_token`` 及 ``prompt``。
    """
    return await _request_collection_change(
        resource_type="music",
        resource_id=resource_id,
        action=action,
        runtime=runtime,
    )


@tool
async def request_playlist_collection_change(
    resource_id: PositiveResourceId,
    action: ConfirmationAction,
    runtime: ToolRuntime,
) -> ToolMessage:
    """请求用户二次确认收藏或取消收藏公开歌单。

    用户表达收藏意图后先调用本工具，绝不能直接执行写操作。不能收藏自己的歌单，
    ID 必须来自查询结果。本工具只生成确认卡片，不会修改收藏状态。

    Args:
        resource_id: 歌单 ID，须来自 ``search_playlist_catalog`` 的返回结果。
        action: 操作类型，``"collect"`` 为收藏，``"uncollect"`` 为取消收藏。

    Returns:
        结构化 ``ToolMessage``。``content`` 为等待确认的摘要文本；``artifact`` 含
        ``type``（``"confirmation_card"``）、``resource_type``、``action``、
        ``resource``（``id``、``title``、``cover_url``）、``confirmation_token`` 及 ``prompt``。
    """
    return await _request_collection_change(
        resource_type="playlist",
        resource_id=resource_id,
        action=action,
        runtime=runtime,
    )


@tool
async def request_album_collection_change(
    resource_id: PositiveResourceId,
    action: ConfirmationAction,
    runtime: ToolRuntime,
) -> ToolMessage:
    """请求用户二次确认收藏或取消收藏专辑。

    用户表达收藏意图后先调用本工具，绝不能直接执行写操作。ID 必须来自查询结果。
    本工具只生成确认卡片，不会修改收藏状态。

    Args:
        resource_id: 专辑 ID，须来自 ``search_album_catalog`` 的返回结果。
        action: 操作类型，``"collect"`` 为收藏，``"uncollect"`` 为取消收藏。

    Returns:
        结构化 ``ToolMessage``。``content`` 为等待确认的摘要文本；``artifact`` 含
        ``type``（``"confirmation_card"``）、``resource_type``、``action``、
        ``resource``（``id``、``title``、``cover_url``）、``confirmation_token`` 及 ``prompt``。
    """
    return await _request_collection_change(
        resource_type="album",
        resource_id=resource_id,
        action=action,
        runtime=runtime,
    )


@tool
async def get_personal_music_context(runtime: ToolRuntime) -> dict[str, object]:
    """获取当前用户的情绪、兴趣、曲风、语言偏好和长期画像。

    个性推荐音乐时必须先调用本工具，分析哪些偏好字段与用户当前需求相关；
    然后调用音乐查询工具筛选候选，最后调用音乐推送工具展示结果。

    Args:
        无；当前用户身份由运行时上下文自动注入。

    Returns:
        用户偏好字典，含 ``emotion_tags``、``interest_tags``、``styles``、
        ``languages``（均为名称字符串列表）及 ``profile``（长期画像文本，可能为空字符串）。
    """
    user_id = _runtime_user_id(runtime)
    async with AsyncSessionLocal() as db:
        emotion_rows = await db.execute(
            select(EmotionTag.name)
            .join(UserEmotionTag, UserEmotionTag.emotion_tag_id == EmotionTag.id)
            .where(UserEmotionTag.user_id == user_id)
        )
        interest_rows = await db.execute(
            select(InterestTag.name)
            .join(UserInterestTag, UserInterestTag.interest_tag_id == InterestTag.id)
            .where(UserInterestTag.user_id == user_id)
        )
        style_rows = await db.execute(
            select(Style.name)
            .join(UserStyle, UserStyle.style_id == Style.id)
            .where(UserStyle.user_id == user_id)
        )
        language_rows = await db.execute(
            select(Language.name)
            .join(UserLanguage, UserLanguage.language_id == Language.id)
            .where(UserLanguage.user_id == user_id)
        )
        profile = (
            await db.execute(
                select(UserProfile.content).where(UserProfile.user_id == user_id)
            )
        ).scalar_one_or_none()
    return {
        "emotion_tags": list(emotion_rows.scalars().all()),
        "interest_tags": list(interest_rows.scalars().all()),
        "styles": list(style_rows.scalars().all()),
        "languages": list(language_rows.scalars().all()),
        "profile": profile or "",
    }


async def _apply_music_collection(
    db: AsyncSession,
    *,
    user_id: int,
    resource_id: int,
    action: ConfirmationAction,
) -> None:
    if action == "uncollect":
        await collection_service.uncollect_music(db, user_id, resource_id)
        return
    if await collection_service.is_music_collected(db, user_id, resource_id):
        return
    playlist = await playlist_service.create_default_like_playlist(db, user_id)
    await playlist_service.add_music_to_playlist(
        db,
        playlist.id,
        resource_id,
        user_id,
    )


async def _apply_collection_payload(
    db: AsyncSession,
    *,
    user_id: int,
    resource_type: ConfirmationResourceType,
    resource_id: int,
    action: ConfirmationAction,
) -> None:
    if resource_type == "music":
        await _apply_music_collection(
            db,
            user_id=user_id,
            resource_id=resource_id,
            action=action,
        )
        return
    if resource_type == "playlist":
        if action == "collect":
            await collection_service.collect_playlist(db, user_id, resource_id)
        else:
            await collection_service.uncollect_playlist(db, user_id, resource_id)
        return
    if action == "collect":
        await collection_service.collect_album(db, user_id, resource_id)
    else:
        await collection_service.uncollect_album(db, user_id, resource_id)


@tool
async def confirm_collection_change(runtime: ToolRuntime) -> str:
    """执行用户刚刚通过确认卡片明确授权的收藏或取消收藏操作。

    仅当当前用户消息携带前端注入的有效确认凭证时调用。不得把普通的“好的”、
    推测性意图或模型自己的判断当作确认；没有有效凭证时本工具会拒绝执行。

    Args:
        无；确认凭证由前端在用户点击确认卡片后注入运行时上下文。

    Returns:
        操作结果文本。成功时说明已完成的收藏或取消收藏；凭证缺失、失效、
        已使用或不属于当前用户时返回拒绝原因，且不修改任何收藏状态。
    """
    user_id = _runtime_user_id(runtime)
    token = runtime.state.get("confirmation_token")
    if not isinstance(token, str) or not token:
        return "未收到有效的二次确认，未执行任何收藏操作。"

    payload = decode_confirmation_token(token, expected_user_id=user_id)
    if payload is None:
        return "二次确认已失效或不属于当前用户，未执行任何收藏操作。"
    if not await reserve_confirmation(payload):
        return "该二次确认已经使用，未重复执行收藏操作。"

    try:
        async with AsyncSessionLocal() as db:
            await _apply_collection_payload(
                db,
                user_id=user_id,
                resource_type=payload["resource_type"],
                resource_id=payload["resource_id"],
                action=payload["action"],
            )
    except Exception:
        await release_confirmation(payload)
        raise

    action_label = "收藏" if payload["action"] == "collect" else "取消收藏"
    resource_label = {
        "music": "音乐",
        "playlist": "歌单",
        "album": "专辑",
    }[payload["resource_type"]]
    return f"已按用户确认完成{resource_label}{action_label}。"
