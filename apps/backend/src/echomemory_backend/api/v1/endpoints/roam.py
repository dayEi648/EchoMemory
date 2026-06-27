"""私人漫游（Private Roam）API 端点。

提供开始漫游、获取状态、导航、收藏、不喜欢、AI 引导、品味总结等操作。
"""

from fastapi import APIRouter, Body

from echomemory_backend.api.deps import ActiveUser, PositiveIntPath, SessionDep
from echomemory_backend.schemas.roam import (
    RoamDislikeReasons,
    RoamGuideRequest,
    RoamGuideResponse,
    RoamReportOut,
    RoamStateOut,
)
from echomemory_backend.services import roam_service

router = APIRouter(prefix="/roam", tags=["roam"])


@router.post("/start", response_model=RoamStateOut)
async def start_roam(
    db: SessionDep,
    current_user: ActiveUser,
):
    """开始新的私人漫游 session。

    清除已有的漫游数据，纯随机选择第一首歌。
    """
    result = await roam_service.start_roam(db, current_user.id)
    return RoamStateOut.model_validate(result)


@router.get("/state", response_model=RoamStateOut)
async def get_roam_state(
    db: SessionDep,
    current_user: ActiveUser,
):
    """获取当前漫游 session 的完整状态。"""
    result = await roam_service.get_roam_state(db, current_user.id)
    return RoamStateOut.model_validate(result)


@router.post("/next", response_model=RoamStateOut)
async def next_song(
    db: SessionDep,
    current_user: ActiveUser,
):
    """下一首。

    在列表末尾时生成新歌（附带 AI 推荐理由），否则纯导航。
    """
    result = await roam_service.next_song_with_reason(db, current_user.id)
    return RoamStateOut.model_validate(result)


@router.post("/prev", response_model=RoamStateOut)
async def prev_song(
    db: SessionDep,
    current_user: ActiveUser,
):
    """上一首（纯导航，不含推荐理由）。"""
    result = await roam_service.prev_song_no_reason(db, current_user.id)
    return RoamStateOut.model_validate(result)


@router.post("/{song_id}/favorite")
async def favorite_song(
    db: SessionDep,
    current_user: ActiveUser,
    song_id: PositiveIntPath,
    playlist_id: int | None = Body(default=None, embed=True),
):
    """收藏当前歌曲到指定歌单。

    未指定 playlist_id 时默认收藏到"我喜欢的音乐"歌单。
    """
    result = await roam_service.favorite_song_with_action(
        db, current_user.id, song_id, playlist_id=playlist_id,
    )
    return result


@router.post("/{song_id}/dislike")
async def dislike_song(
    db: SessionDep,
    current_user: ActiveUser,
    song_id: PositiveIntPath,
    reasons: RoamDislikeReasons | None = None,
):
    """标记不喜欢当前歌曲。

    无 reasons 时仅屏蔽该歌曲；带 reasons 时额外屏蔽指定标签维度。
    """
    result = await roam_service.dislike_song_with_action(
        current_user.id,
        song_id,
        reasons=reasons.model_dump(exclude_none=True) if reasons else None,
    )
    return result


@router.post("/guide", response_model=RoamGuideResponse)
async def guide_roam(
    db: SessionDep,
    current_user: ActiveUser,
    body: RoamGuideRequest,
):
    """自然语言调整漫游方向。

    输入如"我想听有活力的电子乐"，AI 解析后调整偏好池并立即生成新歌。
    """
    result = await roam_service.guide_roam(db, current_user.id, body.hint)
    return RoamGuideResponse.model_validate(result)


@router.post("/end", response_model=RoamReportOut)
async def end_roam(
    db: SessionDep,
    current_user: ActiveUser,
):
    """结束漫游，生成 AI 品味总结报告并清除 session。"""
    result = await roam_service.end_roam(db, current_user.id)
    return RoamReportOut.model_validate(result)
