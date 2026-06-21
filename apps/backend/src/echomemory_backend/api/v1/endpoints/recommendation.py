"""推荐系统 API 端点。

提供每日推荐、私人雷达、推荐歌单、推荐专辑以及推荐榜查询接口。
"""


from fastapi import APIRouter, Query

from echomemory_backend.api.deps import ActiveUser, SessionDep
from echomemory_backend.schemas.album import PaginatedAlbumListOut
from echomemory_backend.schemas.music import (
    PaginatedMusicListOut,
    RecommendChartListOut,
)
from echomemory_backend.schemas.playlist import PaginatedPlaylistListOut
from echomemory_backend.services import (
    collection_service,
    recommendation_service,
)
from echomemory_backend.services.cache_service import (
    get_cached_daily_recommendation,
    get_cached_radar_recommendation,
    get_cached_recommendation_chart,
    set_cached_daily_recommendation,
    set_cached_radar_recommendation,
    set_cached_recommendation_chart,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _today_str() -> str:
    """获取当前 UTC 日期字符串（YYYY-MM-DD）。"""
    return recommendation_service._today().isoformat()


@router.get("/daily", response_model=PaginatedMusicListOut)
async def get_daily_recommendations(
    db: SessionDep,
    current_user: ActiveUser,
):
    """获取当前用户的每日推荐。

    当天首次访问时若尚未生成，会自动生成并持久化。
    """
    cached = await get_cached_daily_recommendation(current_user.id)
    if cached is not None:
        return PaginatedMusicListOut.model_validate(cached)

    musics = await recommendation_service.get_daily_recommendation_musics(
        db, current_user.id
    )
    collected_ids = await collection_service.get_collected_music_ids(
        db, current_user.id, [m.id for m in musics]
    )
    items = []
    for music in musics:
        item = {
            "id": music.id,
            "title": music.title,
            "is_vip": music.is_vip,
            "hot": music.hot,
            "play_count": music.play_count,
            "cover_icon_url": music.cover_icon_url,
            "authors": [
                {
                    "id": a.author.id,
                    "username": a.author.username,
                    "nickname": a.author.nickname,
                    "avatar_url": a.author.avatar_url,
                    "ordinal": a.ordinal,
                }
                for a in music.authors
            ],
            "created_at": music.created_at,
            "is_collected_by_me": music.id in collected_ids,
        }
        items.append(item)

    result = {"items": items, "total": len(items)}
    await set_cached_daily_recommendation(current_user.id, result)
    return PaginatedMusicListOut.model_validate(result)


@router.get("/radar", response_model=PaginatedMusicListOut)
async def get_radar_recommendations(
    db: SessionDep,
    current_user: ActiveUser,
):
    """获取当前用户的私人雷达。

    当天首次访问时若尚未生成，会自动生成并持久化。
    """
    cached = await get_cached_radar_recommendation(current_user.id)
    if cached is not None:
        return PaginatedMusicListOut.model_validate(cached)

    musics = await recommendation_service.get_radar_recommendation_musics(
        db, current_user.id
    )
    collected_ids = await collection_service.get_collected_music_ids(
        db, current_user.id, [m.id for m in musics]
    )
    items = []
    for music in musics:
        item = {
            "id": music.id,
            "title": music.title,
            "is_vip": music.is_vip,
            "hot": music.hot,
            "play_count": music.play_count,
            "cover_icon_url": music.cover_icon_url,
            "authors": [
                {
                    "id": a.author.id,
                    "username": a.author.username,
                    "nickname": a.author.nickname,
                    "avatar_url": a.author.avatar_url,
                    "ordinal": a.ordinal,
                }
                for a in music.authors
            ],
            "created_at": music.created_at,
            "is_collected_by_me": music.id in collected_ids,
        }
        items.append(item)

    result = {"items": items, "total": len(items)}
    await set_cached_radar_recommendation(current_user.id, result)
    return PaginatedMusicListOut.model_validate(result)


@router.get("/playlists", response_model=PaginatedPlaylistListOut)
async def get_recommended_playlists(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """根据当前用户口味推荐公开歌单。"""
    result = await recommendation_service.recommend_playlists(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    playlist_ids = [pl.id for pl in result["items"]]
    collected_ids = await collection_service.get_collected_playlist_ids(
        db, current_user.id, playlist_ids
    )
    items = []
    for playlist in result["items"]:
        items.append(
            {
                "id": playlist.id,
                "title": playlist.title,
                "is_private": playlist.is_private,
                "is_like": playlist.is_like,
                "cover_icon_url": playlist.cover_icon_url,
                "user": {
                    "id": playlist.user.id,
                    "username": playlist.user.username,
                    "nickname": playlist.user.nickname,
                    "avatar_url": playlist.user.avatar_url,
                },
                "created_at": playlist.created_at,
                "is_collected_by_me": playlist.id in collected_ids,
            }
        )
    return {"items": items, "total": result["total"]}


@router.get("/albums", response_model=PaginatedAlbumListOut)
async def get_recommended_albums(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """根据当前用户口味推荐专辑。"""
    result = await recommendation_service.recommend_albums(
        db,
        current_user.id,
        limit=limit,
        offset=offset,
    )
    album_ids = [album.id for album in result["items"]]
    collected_ids = await collection_service.get_collected_album_ids(
        db, current_user.id, album_ids
    )
    items = []
    for album in result["items"]:
        items.append(
            {
                "id": album.id,
                "title": album.title,
                "hot": album.hot,
                "play_count": album.play_count,
                "cover_icon_url": album.cover_icon_url,
                "created_at": album.created_at,
                "is_collected_by_me": album.id in collected_ids,
            }
        )
    return {"items": items, "total": result["total"]}


@router.get("/chart", response_model=RecommendChartListOut)
async def get_recommendation_chart(
    db: SessionDep,
    limit: int = Query(20, ge=1, le=100),
):
    """获取今日推荐榜。

    按今天有多少用户的每日推荐包含该音乐进行排序。
    """
    date_str = _today_str()
    cached = await get_cached_recommendation_chart(date_str)
    if cached is not None:
        return RecommendChartListOut.model_validate(cached)

    chart_rows = await recommendation_service.get_recommendation_chart(
        db, limit=limit
    )
    music_ids = [music.id for music, _ in chart_rows]
    # 推荐榜无需按用户标记收藏，但为保持一致性，未登录也可访问，这里不填充 is_collected_by_me
    items = []
    for music, count in chart_rows:
        items.append(
            {
                "id": music.id,
                "title": music.title,
                "is_vip": music.is_vip,
                "hot": music.hot,
                "play_count": music.play_count,
                "cover_icon_url": music.cover_icon_url,
                "authors": [
                    {
                        "id": a.author.id,
                        "username": a.author.username,
                        "nickname": a.author.nickname,
                        "avatar_url": a.author.avatar_url,
                        "ordinal": a.ordinal,
                    }
                    for a in music.authors
                ],
                "created_at": music.created_at,
                "is_collected_by_me": False,
                "recommend_count": count,
            }
        )

    result = {"items": items}
    await set_cached_recommendation_chart(date_str, result)
    return RecommendChartListOut.model_validate(result)
