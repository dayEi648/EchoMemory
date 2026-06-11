"""用户相关 API 端点，提供用户资料管理、关注关系及管理员操作接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import ActiveUser, AdminUser, OptionalUser, SessionDep
from echomemory_backend.api.v1.endpoints._upload_helpers import upload_optional_image
from echomemory_backend.core import oss_client
from echomemory_backend.core.config import settings
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import (
    FollowCreate,
    FolloweeOut,
    FollowerOut,
    PaginatedFolloweeOut,
    PaginatedFollowerOut,
    PaginatedUserAdminOut,
    PaginatedUserSearchOut,
    UserAdminCreate,
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
    city: str | None = Form(None),
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
    if city is not None:
        data["city"] = city
    return UserUpdate(**data)


@router.patch("/me", response_model=UserMeOut)
async def update_me(
    db: SessionDep,
    current_user: ActiveUser,
    user_in: Annotated[UserUpdate, Depends(_parse_user_update_form)],
    avatar: UploadFile | None = File(None),
) -> User:
    """更新当前用户自己的个人资料。可选上传新头像图片。"""
    avatar_url = await upload_optional_image(
        avatar,
        folder=settings.oss_avatar_prefix,
        prefix=str(current_user.id),
        detail_name="Avatar",
    )

    try:
        return await user_service.update_user_profile(db, current_user, user_in, avatar_url)
    except BusinessError:
        if avatar_url:
            await oss_client.delete_object_by_url(avatar_url)
        raise


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


@router.post("/me/recalculate-tags", status_code=status.HTTP_204_NO_CONTENT)
async def recalculate_my_tags(
    db: SessionDep, current_user: ActiveUser
) -> None:
    """手动触发重新计算当前用户的情绪标签和兴趣标签。"""
    await user_tag_service.recalculate_user_tags(db, current_user.id)
    return None


@router.get("/{user_id}", response_model=UserPublicOut)
async def get_user(
    db: SessionDep, user_id: int, current_user: OptionalUser = None
) -> UserPublicOut:
    """根据用户 ID 获取公开的个人资料。"""
    user = await user_service.get_user_by_id(db, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    followed = False
    if current_user is not None and current_user.id != user_id:
        followed = await user_service.is_following(db, current_user.id, user_id)
    return UserPublicOut.model_validate(user).model_copy(
        update={"is_followed_by_me": followed}
    )


@router.get("/", response_model=PaginatedUserSearchOut)
async def search_users(
    db: SessionDep,
    q: str | None = Query(None, description="按用户名或昵称搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: OptionalUser = None,
):
    """按可选关键词搜索用户。"""
    result = await user_service.search_users(db, q=q, limit=limit, offset=offset)
    users = result["items"]
    followed_ids: set[int] = set()
    if current_user is not None and users:
        followed_ids = await user_service.get_followed_user_ids(
            db, current_user.id, [u.id for u in users]
        )
    items = [
        UserSearchOut.model_validate(u).model_copy(
            update={"is_followed_by_me": u.id in followed_ids}
        )
        for u in users
    ]
    return PaginatedUserSearchOut(items=items, total=result["total"])


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


@router.get("/{user_id}/followees", response_model=PaginatedFolloweeOut)
async def get_followees(
    db: SessionDep,
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """列出指定用户关注的用户列表。"""
    return await user_service.get_followees(db, user_id, limit=limit, offset=offset)


@router.get("/{user_id}/followers", response_model=PaginatedFollowerOut)
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
@router.get("/admin/list", response_model=PaginatedUserAdminOut)
async def admin_list_users(
    db: SessionDep,
    admin: AdminUser,
    status: int | None = Query(None, ge=0, le=3),
    role: int | None = Query(None, ge=0, le=3),
    is_deleted: bool | None = Query(False, description="是否已注销（软删除）；不传默认 false，传 null 显示全部"),
    q: str | None = Query(None, description="按用户名或昵称搜索"),
    sort_by: str = Query("id", description="排序字段: id, created_at, exp, level, like_count"),
    sort_order: str = Query("asc", description="排序方向: asc, desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedUserAdminOut:
    """以管理员身份列出用户，支持筛选、排序和分页。"""
    items, total = await admin_service.list_users_with_count(
        db,
        status=status,
        role=role,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
        is_deleted=is_deleted,
    )
    return PaginatedUserAdminOut(items=items, total=total)


@router.post("/admin/create", response_model=UserMeOut, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    db: SessionDep,
    admin: AdminUser,
    user_in: UserAdminCreate,
) -> User:
    """以管理员身份创建新用户。

    与普通注册不同，管理员可以指定 role、status、safety_score、is_verified、exp 等字段。
    权限规则：管理员不能创建与自己同级或更高级别的用户。
    """
    return await admin_service.create_user_as_admin(db, admin, user_in)


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


@router.get("/{user_id}/admin", response_model=UserMeOut)
async def admin_get_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
) -> User:
    """以管理员身份获取单个用户的完整信息。"""
    return await admin_service.get_user_full(db, admin, user_id)


@router.delete("/{user_id}/admin", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
) -> None:
    """以管理员身份硬删除用户及其所有关联数据。"""
    await admin_service.hard_delete_user(db, admin, user_id)
    return None
