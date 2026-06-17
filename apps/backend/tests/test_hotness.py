"""热度计算回归测试。"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.album import Album
from echomemory_backend.models.music import Music
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.user import User
from echomemory_backend.services.hotness_service import (
    recalculate_album_hot,
    recalculate_music_hot,
    recalculate_playlist_hot,
)


async def _create_user(db: AsyncSession, username: str) -> User:
    user = User(username=username, password_hash="hashed", nickname=username)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_music(db: AsyncSession, title: str, **kwargs) -> Music:
    music = Music(title=title, is_published=True, **kwargs)
    db.add(music)
    await db.commit()
    await db.refresh(music)
    return music


async def test_music_hot_uses_recent_play_count_sum(db_session: AsyncSession):
    """近 7 天热度应累计 play_history.play_count，而不是统计历史行数。"""
    user = await _create_user(db_session, "hot_counter")
    music = await _create_music(db_session, "RecentPlayCountSong")
    db_session.add(
        PlayHistory(
            user_id=user.id,
            music_id=music.id,
            play_count=5,
            played_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    await db_session.commit()

    await recalculate_music_hot(db_session, music.id)
    await db_session.commit()
    await db_session.refresh(music)

    assert music.hot > 300


async def test_music_hot_includes_lifetime_play_count_for_old_music(
    db_session: AsyncSession,
):
    """老歌应能通过全期播放量获得经典权重。"""
    music = await _create_music(
        db_session,
        "ClassicSong",
        release_date=date.today() - timedelta(days=3650),
        play_count=10000,
    )

    await recalculate_music_hot(db_session, music.id)
    await db_session.commit()
    await db_session.refresh(music)

    assert music.hot > 0


async def test_album_hot_uses_own_engagement_not_child_average(
    db_session: AsyncSession,
):
    """专辑热度应按自身互动计算，不依赖所含音乐热度平均值。"""
    album = Album(title="SelfHotAlbum", collect_count=20, play_count=50)
    db_session.add(album)
    await db_session.commit()
    await db_session.refresh(album)

    await recalculate_album_hot(db_session, album.id)
    await db_session.commit()
    await db_session.refresh(album)

    assert album.hot > 0


async def test_playlist_hot_uses_own_engagement_not_child_average(
    db_session: AsyncSession,
):
    """歌单热度应按自身互动计算，不依赖所含音乐热度平均值。"""
    user = await _create_user(db_session, "playlist_hot_owner")
    playlist = Playlist(
        title="SelfHotPlaylist",
        user_id=user.id,
        collect_count=20,
        play_count=50,
        comment_count=5,
    )
    db_session.add(playlist)
    await db_session.commit()
    await db_session.refresh(playlist)

    await recalculate_playlist_hot(db_session, playlist.id)
    await db_session.commit()
    await db_session.refresh(playlist)

    assert playlist.hot > 0
