from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import ActiveUser, AdminUser, SessionDep
from echomemory_backend.core import oss_client
from echomemory_backend.core.config import settings
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import (
    FollowCreate,
    FolloweeOut,
    FollowerOut,
    UserAdminUpdate,
    UserBanAction,
    UserMeOut,
    UserPublicOut,
    UserSearchOut,
    UserUpdate,
)
from echomemory_backend.schemas.user_tag import UserTagOut
from echomemory_backend.services import admin_service
from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.services import user_service
from echomemory_backend.services import user_tag_service

router = APIRouter(prefix="/users", tags=["users"])


def _parse_user_update_form(
    nickname: str | None = Form(None, min_length=1, max_length=32),
    email: str | None = Form(None),
    phone: str | None = Form(None, max_length=20),
    gender: int | None = Form(None, ge=0, le=2),
    birth: str | None = Form(None),
    bio: str | None = Form(None),
    city_id: int | None = Form(None),
) -> UserUpdate:
    """将 multipart form 字段解析为 UserUpdate Schema。"""
    data = {}
    if nickname is not None:
        data["nickname"] = nickname
    if email is not None:
        data["email"] = email
    if phone is not None:
        data["phone"] = phone
    if gender is not None:
        data["gender"] = gender
    if birth is not None:
        data["birth"] = birth
    if bio is not None:
        data["bio"] = bio
    if city_id is not None:
        data["city_id"] = city_id
    return UserUpdate(**data)


@router.patch("/me", response_model=UserMeOut)
async def update_me(
    db: SessionDep,
    current_user: ActiveUser,
    user_in: Annotated[UserUpdate, Depends(_parse_user_update_form)],
    avatar: UploadFile | None = File(None),
) -> User:
    """更新当前用户自己的个人资料。可选上传新头像图片。"""
    avatar_url: str | None = None
    if avatar is not None:
        if avatar.content_type is None or not avatar.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Avatar must be an image file",
            )
        try:
            avatar_url = await oss_client.upload_image_to_oss(
                avatar.file,
                folder=settings.oss_avatar_prefix,
                filename_prefix=str(current_user.id),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    try:
        return await user_service.update_user_profile(db, current_user, user_in, avatar_url)
    except BusinessError as exc:
        if avatar_url:
            await oss_client.delete_object_by_url(avatar_url)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/me/emotion-tags", response_model=list[UserTagOut])
async def get_my_emotion_tags(
    db: SessionDep, current_user: ActiveUser
) -> list[dict]:
    """获取当前用户的情感标签偏好列表。"""
    return await user_tag_service.list_user_emotion_tags(db, current_user.id)


@router.get("/me/interest-tags", response_model=list[UserTagOut])
async def get_my_interest_tags(
    db: SessionDep, current_user: ActiveUser
) -> list[dict]:
    """获取当前用户的兴趣标签偏好列表。"""
    return await user_tag_service.list_user_interest_tags(db, current_user.id)


@router.get("/{user_id}", response_model=UserPublicOut)
async def get_user(db: SessionDep, user_id: int) -> User:
    """根据用户 ID 获取公开的个人资料。"""
    user = await user_service.get_user_by_id(db, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get("/", response_model=list[UserSearchOut])
async def search_users(
    db: SessionDep,
    q: str | None = Query(None, description="按用户名或昵称搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """按可选关键词搜索用户。"""
    return await user_service.search_users(db, q=q, limit=limit, offset=offset)


@router.post("/follow", status_code=status.HTTP_204_NO_CONTENT)
async def follow_user(
    db: SessionDep, current_user: ActiveUser, follow_in: FollowCreate
) -> None:
    """关注另一个用户。"""
    await user_service.follow_user(db, current_user.id, follow_in.followee_id)
    return None


@router.post("/unfollow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_user(
    db: SessionDep, current_user: ActiveUser, follow_in: FollowCreate
) -> None:
    """取消关注某用户。"""
    await user_service.unfollow_user(db, current_user.id, follow_in.followee_id)
    return None


@router.get("/{user_id}/followees", response_model=list[FolloweeOut])
async def get_followees(
    db: SessionDep,
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """列出指定用户关注的用户列表。"""
    return await user_service.get_followees(db, user_id, limit=limit, offset=offset)


@router.get("/{user_id}/followers", response_model=list[FollowerOut])
async def get_followers(
    db: SessionDep,
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """列出关注指定用户的用户列表。"""
    return await user_service.get_followers(db, user_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# 管理员接口
# ---------------------------------------------------------------------------
@router.get("/admin/list", response_model=list[UserMeOut])
async def admin_list_users(
    db: SessionDep,
    admin: AdminUser,
    status: int | None = Query(None, ge=0, le=3),
    role: int | None = Query(None, ge=0, le=3),
    q: str | None = Query(None, description="按用户名或昵称搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """以管理员身份列出用户，支持筛选。"""
    return await admin_service.list_users(
        db, status=status, role=role, q=q, limit=limit, offset=offset
    )


@router.patch("/{user_id}/admin", response_model=UserMeOut)
async def admin_update_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
    user_in: UserAdminUpdate,
) -> User:
    """以管理员身份更新用户信息。"""
    return await admin_service.update_user_as_admin(db, admin, user_id, user_in)


@router.post("/{user_id}/ban", response_model=UserMeOut)
async def admin_ban_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
    action: UserBanAction,
) -> User:
    """封禁用户。"""
    return await admin_service.ban_user(db, admin, user_id, action)


@router.post("/{user_id}/unban", response_model=UserMeOut)
async def admin_unban_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
) -> User:
    """解封用户。"""
    return await admin_service.unban_user(db, admin, user_id)
