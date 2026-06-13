"""用户标签服务模块，负责根据听歌历史与歌单重新计算并管理用户的偏好画像。"""

from collections import Counter

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.music import (
    Music,
    MusicEmotionTag,
    MusicInterestTag,
)
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.models.user_tag import (
    UserEmotionTag,
    UserInterestTag,
    UserLanguage,
    UserStyle,
)


def _top_tag_ids_with_tie(counter: Counter, min_rank: int = 5) -> list[int]:
    """从 Counter 中按频率取前 N 个标签 ID，第 N 名并列时全部保留。

    Args:
        counter: 标签 ID 到出现次数的计数器。
        min_rank: 最低保留名次，默认 5。

    Returns:
        保留的标签 ID 列表，按频率降序排列。
    """
    if not counter:
        return []
    sorted_items = counter.most_common()
    if len(sorted_items) <= min_rank:
        return [tag_id for tag_id, _ in sorted_items]
    threshold = sorted_items[min_rank - 1][1]
    return [tag_id for tag_id, count in sorted_items if count >= threshold]


async def recalculate_user_tags(
    db: AsyncSession, user_id: int, *, commit: bool = True
) -> None:
    """根据用户听歌历史和歌单，重新计算并覆盖写入用户的偏好画像。

    情绪标签、兴趣标签、风格偏好、语言偏好独立计算。听歌历史中的音乐按
    其播放次数加权，歌单中的音乐权重为 1。各自按出现频率排序，保留频率
    最高的 5 个；若第 5 名存在并列，则并列标签全部保留。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 要重新计算标签的用户主键。
        commit: 是否在计算完成后自动提交事务，默认 True。
            若由外部事务统一控制，可传入 False。
    """
    # ------------------------------------------------------------------
    # 情绪标签
    # ------------------------------------------------------------------
    stmt_history_emotion = (
        select(MusicEmotionTag.emotion_tag_id, PlayHistory.play_count)
        .join(PlayHistory, PlayHistory.music_id == MusicEmotionTag.music_id)
        .where(PlayHistory.user_id == user_id)
    )
    history_emotion_rows = list((await db.execute(stmt_history_emotion)).all())

    stmt_playlist_emotion = (
        select(PlaylistEmotionTag.emotion_tag_id)
        .join(Playlist, Playlist.id == PlaylistEmotionTag.playlist_id)
        .where(Playlist.user_id == user_id)
    )
    playlist_emotion_ids = list((await db.execute(stmt_playlist_emotion)).scalars().all())

    emotion_counter = Counter()
    for tag_id, play_count in history_emotion_rows:
        emotion_counter[tag_id] += play_count
    for tag_id in playlist_emotion_ids:
        emotion_counter[tag_id] += 1
    top_emotion_ids = _top_tag_ids_with_tie(emotion_counter)

    # ------------------------------------------------------------------
    # 兴趣标签
    # ------------------------------------------------------------------
    stmt_history_interest = (
        select(MusicInterestTag.interest_tag_id, PlayHistory.play_count)
        .join(PlayHistory, PlayHistory.music_id == MusicInterestTag.music_id)
        .where(PlayHistory.user_id == user_id)
    )
    history_interest_rows = list((await db.execute(stmt_history_interest)).all())

    stmt_playlist_interest = (
        select(PlaylistInterestTag.interest_tag_id)
        .join(Playlist, Playlist.id == PlaylistInterestTag.playlist_id)
        .where(Playlist.user_id == user_id)
    )
    playlist_interest_ids = list((await db.execute(stmt_playlist_interest)).scalars().all())

    interest_counter = Counter()
    for tag_id, play_count in history_interest_rows:
        interest_counter[tag_id] += play_count
    for tag_id in playlist_interest_ids:
        interest_counter[tag_id] += 1
    top_interest_ids = _top_tag_ids_with_tie(interest_counter)

    # ------------------------------------------------------------------
    # 风格偏好
    # ------------------------------------------------------------------
    stmt_history_style = (
        select(Music.style_id, PlayHistory.play_count)
        .join(PlayHistory, PlayHistory.music_id == Music.id)
        .where(PlayHistory.user_id == user_id, Music.style_id.is_not(None))
    )
    history_style_rows = list((await db.execute(stmt_history_style)).all())

    stmt_playlist_style = (
        select(Music.style_id)
        .join(PlaylistMusic, PlaylistMusic.music_id == Music.id)
        .join(Playlist, Playlist.id == PlaylistMusic.playlist_id)
        .where(Playlist.user_id == user_id, Music.style_id.is_not(None))
    )
    playlist_style_ids = list((await db.execute(stmt_playlist_style)).scalars().all())

    style_counter = Counter()
    for style_id, play_count in history_style_rows:
        style_counter[style_id] += play_count
    for style_id in playlist_style_ids:
        style_counter[style_id] += 1
    top_style_ids = _top_tag_ids_with_tie(style_counter)

    # ------------------------------------------------------------------
    # 语言偏好
    # ------------------------------------------------------------------
    stmt_history_language = (
        select(Music.language_id, PlayHistory.play_count)
        .join(PlayHistory, PlayHistory.music_id == Music.id)
        .where(PlayHistory.user_id == user_id, Music.language_id.is_not(None))
    )
    history_language_rows = list((await db.execute(stmt_history_language)).all())

    stmt_playlist_language = (
        select(Music.language_id)
        .join(PlaylistMusic, PlaylistMusic.music_id == Music.id)
        .join(Playlist, Playlist.id == PlaylistMusic.playlist_id)
        .where(Playlist.user_id == user_id, Music.language_id.is_not(None))
    )
    playlist_language_ids = list((await db.execute(stmt_playlist_language)).scalars().all())

    language_counter = Counter()
    for language_id, play_count in history_language_rows:
        language_counter[language_id] += play_count
    for language_id in playlist_language_ids:
        language_counter[language_id] += 1
    top_language_ids = _top_tag_ids_with_tie(language_counter)

    # ------------------------------------------------------------------
    # 覆盖写入
    # ------------------------------------------------------------------
    await db.execute(delete(UserEmotionTag).where(UserEmotionTag.user_id == user_id))
    await db.execute(delete(UserInterestTag).where(UserInterestTag.user_id == user_id))
    await db.execute(delete(UserStyle).where(UserStyle.user_id == user_id))
    await db.execute(delete(UserLanguage).where(UserLanguage.user_id == user_id))

    for tag_id in top_emotion_ids:
        db.add(UserEmotionTag(user_id=user_id, emotion_tag_id=tag_id))
    for tag_id in top_interest_ids:
        db.add(UserInterestTag(user_id=user_id, interest_tag_id=tag_id))
    for style_id in top_style_ids:
        db.add(UserStyle(user_id=user_id, style_id=style_id))
    for language_id in top_language_ids:
        db.add(UserLanguage(user_id=user_id, language_id=language_id))

    if commit:
        await db.commit()


async def list_user_emotion_tags(db: AsyncSession, user_id: int) -> list[dict]:
    """查询指定用户的情感标签列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        按绑定时间倒序排列的标签字典列表，每项包含 tag_id、name、created_at。
    """
    result = await db.execute(
        select(UserEmotionTag)
        .where(UserEmotionTag.user_id == user_id)
        .options(selectinload(UserEmotionTag.emotion_tag))
        .order_by(desc(UserEmotionTag.created_at))
    )
    items = result.scalars().all()
    return [
        {
            "tag_id": item.emotion_tag_id,
            "name": item.emotion_tag.name,
            "created_at": item.created_at,
        }
        for item in items
    ]


async def list_user_interest_tags(db: AsyncSession, user_id: int) -> list[dict]:
    """查询指定用户的兴趣标签列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        按绑定时间倒序排列的标签字典列表，每项包含 tag_id、name、created_at。
    """
    result = await db.execute(
        select(UserInterestTag)
        .where(UserInterestTag.user_id == user_id)
        .options(selectinload(UserInterestTag.interest_tag))
        .order_by(desc(UserInterestTag.created_at))
    )
    items = result.scalars().all()
    return [
        {
            "tag_id": item.interest_tag_id,
            "name": item.interest_tag.name,
            "created_at": item.created_at,
        }
        for item in items
    ]


async def list_user_styles(db: AsyncSession, user_id: int) -> list[dict]:
    """查询指定用户的风格偏好列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        按绑定时间倒序排列的风格字典列表，每项包含 tag_id、name、created_at。
    """
    result = await db.execute(
        select(UserStyle)
        .where(UserStyle.user_id == user_id)
        .options(selectinload(UserStyle.style))
        .order_by(desc(UserStyle.created_at))
    )
    items = result.scalars().all()
    return [
        {
            "tag_id": item.style_id,
            "name": item.style.name,
            "created_at": item.created_at,
        }
        for item in items
    ]


async def list_user_languages(db: AsyncSession, user_id: int) -> list[dict]:
    """查询指定用户的语言偏好列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        按绑定时间倒序排列的语言字典列表，每项包含 tag_id、name、created_at。
    """
    result = await db.execute(
        select(UserLanguage)
        .where(UserLanguage.user_id == user_id)
        .options(selectinload(UserLanguage.language))
        .order_by(desc(UserLanguage.created_at))
    )
    items = result.scalars().all()
    return [
        {
            "tag_id": item.language_id,
            "name": item.language.name,
            "created_at": item.created_at,
        }
        for item in items
    ]
