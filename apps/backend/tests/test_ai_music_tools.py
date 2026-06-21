"""AI 音乐目录、推送、收藏确认与个性化上下文工具测试。"""

from __future__ import annotations

from datetime import date

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.ai.tools.music_catalog import (
    confirm_collection_change,
    get_personal_music_context,
    push_album_cards,
    push_music_cards,
    push_playlist_cards,
    request_album_collection_change,
    request_music_collection_change,
    request_playlist_collection_change,
    search_album_catalog,
    search_music_catalog,
    search_playlist_catalog,
)
from echomemory_backend.ai.tools import music_catalog as music_catalog_module
from echomemory_backend.ai.tools import get_tool_registry
from echomemory_backend.models.album import Album, AlbumAuthor, AlbumMusic
from echomemory_backend.models.dictionary import EmotionTag, Language, Style
from echomemory_backend.models.music import Music, MusicAuthor, MusicEmotionTag
from echomemory_backend.models.collection import UserMusicLike
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.models.user import User
from echomemory_backend.models.user_profile import UserProfile
from echomemory_backend.models.user_tag import UserEmotionTag, UserStyle


@pytest.fixture(autouse=True)
def use_test_session_for_tools(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """让工具复用当前测试事件循环中的 Session，避免全局连接池跨 loop。"""

    class _SessionContext:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        music_catalog_module,
        "AsyncSessionLocal",
        lambda: _SessionContext(),
    )


async def _create_user(db: AsyncSession, username: str) -> User:
    user = User(
        username=username,
        nickname=f"{username}-昵称",
        password_hash="hash",
        gender=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _runtime(user_id: int, *, confirmation_token: str | None = None) -> ToolRuntime:
    return ToolRuntime(
        state={
            "user_id": user_id,
            "confirmation_token": confirmation_token,
            "messages": [HumanMessage(content="测试")],
        },
        context=None,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-test",
        store=None,
        tools=[],
    )


async def test_search_music_catalog_only_returns_published_and_supports_filters(
    db_session: AsyncSession,
):
    author = await _create_user(db_session, "catalog_author")
    style = (await db_session.execute(select(Style).limit(1))).scalar_one()
    language = (await db_session.execute(select(Language).limit(1))).scalar_one()
    emotion = (await db_session.execute(select(EmotionTag).limit(1))).scalar_one()
    assert style is not None and language is not None and emotion is not None

    published = Music(
        title="星河回声",
        is_published=True,
        style_id=style.id,
        language_id=language.id,
        release_date=date(2026, 6, 1),
        hot=321,
    )
    unpublished = Music(
        title="星河回声未上架",
        is_published=False,
        style_id=style.id,
        language_id=language.id,
    )
    db_session.add_all([published, unpublished])
    await db_session.flush()
    db_session.add_all(
        [
            MusicAuthor(music_id=published.id, author_id=author.id, ordinal=0),
            MusicAuthor(music_id=unpublished.id, author_id=author.id, ordinal=0),
            MusicEmotionTag(
                music_id=published.id,
                emotion_tag_id=emotion.id,
            ),
        ]
    )
    await db_session.commit()

    result = await search_music_catalog.ainvoke(
        {
            "title": "星河",
            "match_mode": "fuzzy",
            "author": "昵称",
            "styles": [style.name],
            "languages": [language.name],
            "emotion_tags": [emotion.name],
            "limit": 10,
        }
    )

    assert result["total"] == 1
    assert result["items"] == [
        {
            "id": published.id,
            "title": "星河回声",
            "authors": [author.nickname],
            "album": None,
            "style": style.name,
            "language": language.name,
            "emotion_tags": [emotion.name],
            "interest_tags": [],
            "instruments": [],
            "is_vip": False,
            "release_date": "2026-06-01",
            "hot": 321,
        }
    ]
    assert "updated_at" not in result["items"][0]
    assert "file_url" not in result["items"][0]


async def test_search_playlist_catalog_excludes_private_like_and_empty_playlists(
    db_session: AsyncSession,
):
    owner = await _create_user(db_session, "playlist_owner")
    music = Music(title="可见歌曲", is_published=True)
    public = Playlist(title="公开歌单", user_id=owner.id, is_private=False)
    private = Playlist(title="私密歌单", user_id=owner.id, is_private=True)
    like = Playlist(
        title="我喜欢的音乐",
        user_id=owner.id,
        is_private=False,
        is_like=True,
    )
    empty = Playlist(title="空歌单", user_id=owner.id, is_private=False)
    db_session.add_all([music, public, private, like, empty])
    await db_session.flush()
    db_session.add_all(
        [
            PlaylistMusic(playlist_id=public.id, music_id=music.id, ordinal=0),
            PlaylistMusic(playlist_id=private.id, music_id=music.id, ordinal=0),
            PlaylistMusic(playlist_id=like.id, music_id=music.id, ordinal=0),
        ]
    )
    await db_session.commit()

    result = await search_playlist_catalog.ainvoke(
        {"title": "歌单", "match_mode": "fuzzy", "limit": 10}
    )

    assert result["total"] == 1
    assert result["items"][0]["id"] == public.id
    assert result["items"][0]["title"] == "公开歌单"
    assert result["items"][0]["music_count"] == 1


async def test_search_album_catalog_requires_visible_album_with_published_music(
    db_session: AsyncSession,
):
    author = await _create_user(db_session, "album_author")
    published = Music(title="已上架", is_published=True)
    unpublished = Music(title="未上架", is_published=False)
    visible = Album(title="可见专辑")
    hidden = Album(title="仅未上架专辑")
    deleted = Album(title="已删除专辑", is_deleted=True)
    db_session.add_all([published, unpublished, visible, hidden, deleted])
    await db_session.flush()
    db_session.add_all(
        [
            AlbumAuthor(album_id=visible.id, author_id=author.id, ordinal=0),
            AlbumMusic(album_id=visible.id, music_id=published.id, ordinal=0),
            AlbumMusic(album_id=hidden.id, music_id=unpublished.id, ordinal=0),
        ]
    )
    await db_session.commit()

    result = await search_album_catalog.ainvoke(
        {"title": "专辑", "match_mode": "fuzzy", "limit": 10}
    )

    assert result["total"] == 1
    assert result["items"][0]["id"] == visible.id
    assert result["items"][0]["authors"] == [author.nickname]
    assert result["items"][0]["music_count"] == 1


@pytest.mark.parametrize(
    ("tool", "artifact_type"),
    [
        (push_music_cards, "music_card"),
        (push_playlist_cards, "playlist_card"),
        (push_album_cards, "album_card"),
    ],
)
async def test_push_tools_return_persistable_tool_message_artifacts(
    db_session: AsyncSession,
    tool,
    artifact_type: str,
):
    owner = await _create_user(db_session, f"{artifact_type}_owner")
    music = Music(title="推送歌曲", is_published=True)
    playlist = Playlist(title="推送歌单", user_id=owner.id, is_private=False)
    album = Album(title="推送专辑")
    db_session.add_all([music, playlist, album])
    await db_session.flush()
    db_session.add_all(
        [
            PlaylistMusic(playlist_id=playlist.id, music_id=music.id, ordinal=0),
            AlbumMusic(album_id=album.id, music_id=music.id, ordinal=0),
        ]
    )
    await db_session.commit()

    resource_id = {
        "music_card": music.id,
        "playlist_card": playlist.id,
        "album_card": album.id,
    }[artifact_type]
    result = await tool.ainvoke(
        {
            "name": tool.name,
            "id": "call-test",
            "type": "tool_call",
            "args": {
                "resource_ids": [resource_id],
                "runtime": _runtime(owner.id),
            },
        }
    )

    assert isinstance(result, ToolMessage)
    assert result.artifact["version"] == 1
    assert result.artifact["type"] == artifact_type
    assert result.artifact["items"][0]["id"] == resource_id


@pytest.mark.parametrize(
    ("tool", "resource_type"),
    [
        (request_music_collection_change, "music"),
        (request_playlist_collection_change, "playlist"),
        (request_album_collection_change, "album"),
    ],
)
async def test_collection_request_tools_create_confirmation_artifact_without_writing(
    db_session: AsyncSession,
    tool,
    resource_type: str,
):
    user = await _create_user(db_session, f"confirm_{resource_type}_user")
    owner = await _create_user(db_session, f"confirm_{resource_type}_owner")
    music = Music(title="待确认歌曲", is_published=True)
    playlist = Playlist(title="待确认歌单", user_id=owner.id, is_private=False)
    album = Album(title="待确认专辑")
    db_session.add_all([music, playlist, album])
    await db_session.flush()
    db_session.add_all(
        [
            PlaylistMusic(playlist_id=playlist.id, music_id=music.id, ordinal=0),
            AlbumMusic(album_id=album.id, music_id=music.id, ordinal=0),
        ]
    )
    await db_session.commit()
    resource_id = {
        "music": music.id,
        "playlist": playlist.id,
        "album": album.id,
    }[resource_type]

    result = await tool.ainvoke(
        {
            "name": tool.name,
            "args": {
                "resource_id": resource_id,
                "action": "collect",
                "runtime": _runtime(user.id),
            },
            "id": "call-test",
            "type": "tool_call",
        }
    )

    assert isinstance(result, ToolMessage)
    assert result.artifact["type"] == "confirmation_card"
    assert result.artifact["resource_type"] == resource_type
    assert result.artifact["action"] == "collect"
    assert result.artifact["confirmation_token"]


async def test_personal_context_returns_names_and_profile_without_internal_fields(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "personal_context_user")
    emotion = (await db_session.execute(select(EmotionTag).limit(1))).scalar_one()
    style = (await db_session.execute(select(Style).limit(1))).scalar_one()
    assert emotion is not None and style is not None
    db_session.add_all(
        [
            UserEmotionTag(user_id=user.id, emotion_tag_id=emotion.id),
            UserStyle(user_id=user.id, style_id=style.id),
            UserProfile(user_id=user.id, content="偏爱安静、温暖的夜间音乐。"),
        ]
    )
    await db_session.commit()

    result = await get_personal_music_context.coroutine(runtime=_runtime(user.id))

    assert result["emotion_tags"] == [emotion.name]
    assert result["styles"] == [style.name]
    assert result["profile"] == "偏爱安静、温暖的夜间音乐。"
    assert "user_id" not in result
    assert "updated_at" not in result


def test_tool_runtime_parameters_are_hidden_from_model_schema():
    schemas = [
        push_music_cards.tool_call_schema.model_json_schema(),
        request_music_collection_change.tool_call_schema.model_json_schema(),
        get_personal_music_context.tool_call_schema.model_json_schema(),
    ]

    assert all("runtime" not in schema.get("properties", {}) for schema in schemas)


def test_all_music_platform_tools_are_registered_with_expected_metadata():
    registry = get_tool_registry()
    read_tools = {
        "search_music_catalog",
        "search_playlist_catalog",
        "search_album_catalog",
        "push_music_cards",
        "push_playlist_cards",
        "push_album_cards",
        "get_personal_music_context",
    }
    write_tools = {
        "request_music_collection_change",
        "request_playlist_collection_change",
        "request_album_collection_change",
        "confirm_collection_change",
    }

    assert all(registry.is_registered(name) for name in read_tools | write_tools)
    assert all(registry.get_metadata(name).read_only for name in read_tools)
    assert all(not registry.get_metadata(name).read_only for name in write_tools)
    assert all(
        "music-platform" in registry.get_metadata(name).tags
        for name in read_tools | write_tools
    )


async def test_confirm_collection_change_requires_frontend_confirmation_and_is_single_use(
    db_session: AsyncSession,
    fake_redis,
):
    user = await _create_user(db_session, "confirmed_music_user")
    music = Music(title="确认后收藏", is_published=True)
    db_session.add(music)
    await db_session.commit()
    await db_session.refresh(music)

    without_confirmation = await confirm_collection_change.coroutine(
        runtime=_runtime(user.id)
    )
    assert "未收到有效" in without_confirmation
    assert await db_session.get(UserMusicLike, (user.id, music.id)) is None

    request = await request_music_collection_change.coroutine(
        resource_id=music.id,
        action="collect",
        runtime=_runtime(user.id),
    )
    token = request.artifact["confirmation_token"]

    applied = await confirm_collection_change.coroutine(
        runtime=_runtime(user.id, confirmation_token=token)
    )
    assert "已按用户确认完成" in applied
    assert await db_session.get(UserMusicLike, (user.id, music.id)) is not None

    replayed = await confirm_collection_change.coroutine(
        runtime=_runtime(user.id, confirmation_token=token)
    )
    assert "已经使用" in replayed
