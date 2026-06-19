"""评论模块测试 —— TDD：先写测试，再写实现。"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.comment import Comment, CommentDislike, CommentLike
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.models.user import User
from tests.api_helpers import api_data

BASE_URL = "/api/v1/comments"


async def _create_user(
    db: AsyncSession,
    username: str,
    role: int = UserRole.USER.value,
) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash("secret"),
        nickname=username,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


async def _create_music_directly(
    db: AsyncSession,
    title: str = "TestSong",
    is_published: bool = True,
) -> Music:
    music = Music(
        title=title,
        is_published=is_published,
        file_url="https://oss.example.com/musics/test.mp3",
        cover_icon_url="https://oss.example.com/covers/icon.jpg",
    )
    db.add(music)
    await db.commit()
    await db.refresh(music)
    return music


async def _create_playlist_directly(
    db: AsyncSession,
    user_id: int,
    title: str = "TestPlaylist",
    is_private: bool = False,
) -> Playlist:
    playlist = Playlist(
        title=title,
        user_id=user_id,
        is_private=is_private,
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist


async def _create_space_post_directly(
    db: AsyncSession,
    user_id: int,
    content: str = "Test space post",
) -> SpacePost:
    post = SpacePost(
        user_id=user_id,
        content=content,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def _create_comment_directly(
    db: AsyncSession,
    user_id: int,
    content: str = "Test comment",
    music_id: int | None = None,
    playlist_id: int | None = None,
    space_post_id: int | None = None,
    parent_id: int | None = None,
    root_id: int | None = None,
    is_nested_reply: bool = False,
    is_deleted: bool = False,
) -> Comment:
    comment = Comment(
        user_id=user_id,
        content=content,
        music_id=music_id,
        playlist_id=playlist_id,
        space_post_id=space_post_id,
        parent_id=parent_id,
        root_id=root_id,
        is_nested_reply=is_nested_reply,
        is_deleted=is_deleted,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


# ============================================================================
# 发表评论
# ============================================================================


class TestCreateComment:
    """测试发表评论相关功能。"""

    async def test_create_comment_on_music(self, client: TestClient, db_session: AsyncSession):
        """测试正常在音乐下发表评论。"""
        user = await _create_user(db_session, "comment_music_user")
        music = await _create_music_directly(db_session, title="SongToComment")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Great song!",
            },
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["content"] == "Great song!"
        assert data["user"]["id"] == user.id
        assert data["parent_id"] is None

    async def test_create_comment_on_playlist(self, client: TestClient, db_session: AsyncSession):
        """测试正常在歌单下发表评论。"""
        user = await _create_user(db_session, "comment_pl_user")
        owner = await _create_user(db_session, "comment_pl_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PLToComment")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "playlist",
                "target_id": playlist.id,
                "content": "Nice playlist",
            },
        )
        assert resp.status_code == 201
        assert api_data(resp)["content"] == "Nice playlist"

    async def test_create_comment_on_space_post(self, client: TestClient, db_session: AsyncSession):
        """测试正常在动态下发表评论。"""
        user = await _create_user(db_session, "comment_sp_user")
        owner = await _create_user(db_session, "comment_sp_owner")
        post = await _create_space_post_directly(db_session, owner.id, content="Original post")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "space_post",
                "target_id": post.id,
                "content": "Nice post",
            },
        )
        assert resp.status_code == 201
        assert api_data(resp)["content"] == "Nice post"

    async def test_create_reply_to_root(self, client: TestClient, db_session: AsyncSession):
        """测试对根评论发起一级回复。"""
        user = await _create_user(db_session, "reply_user")
        music = await _create_music_directly(db_session, title="SongWithReply")
        root = await _create_comment_directly(
            db_session, user.id, "Root comment", music_id=music.id
        )

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "This is a reply",
                "parent_id": root.id,
            },
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["content"] == "This is a reply"
        assert data["parent_id"] == root.id
        assert data["root_id"] == root.id
        assert data["is_nested_reply"] is False

    async def test_create_nested_reply(self, client: TestClient, db_session: AsyncSession):
        """测试对回复发起嵌套回复（二级及以上）。"""
        user = await _create_user(db_session, "nested_reply_user")
        music = await _create_music_directly(db_session, title="SongWithNested")
        root = await _create_comment_directly(
            db_session, user.id, "Root comment", music_id=music.id
        )
        reply = await _create_comment_directly(
            db_session, user.id, "First reply", music_id=music.id, parent_id=root.id, root_id=root.id
        )

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Nested reply",
                "parent_id": reply.id,
            },
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["parent_id"] == reply.id
        assert data["root_id"] == root.id
        assert data["is_nested_reply"] is True

    async def test_create_comment_invalid_target_type(self, client: TestClient, db_session: AsyncSession):
        """测试使用无效目标类型发表评论时返回 400。"""
        user = await _create_user(db_session, "comment_invalid_type")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "invalid",
                "target_id": 1,
                "content": "Test",
            },
        )
        assert resp.status_code == 400

    async def test_create_comment_nonexistent_target(self, client: TestClient, db_session: AsyncSession):
        """测试对不存在的目标发表评论时返回 404。"""
        user = await _create_user(db_session, "comment_nx_target")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": 99999,
                "content": "Test",
            },
        )
        assert resp.status_code == 404

    async def test_create_comment_unpublished_music(self, client: TestClient, db_session: AsyncSession):
        """测试对未发布的音乐发表评论时返回 404。"""
        user = await _create_user(db_session, "comment_unpub")
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Test",
            },
        )
        assert resp.status_code == 404

    async def test_create_comment_on_private_playlist_by_non_owner(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试非所有者对私密歌单发表评论时返回 404。"""
        user = await _create_user(db_session, "comment_private_pl")
        owner = await _create_user(db_session, "comment_private_pl_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PrivatePL", is_private=True)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "playlist",
                "target_id": playlist.id,
                "content": "Test",
            },
        )
        assert resp.status_code == 404

    async def test_create_comment_on_own_private_playlist(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试歌单所有者在私密歌单下发表评论成功。"""
        owner = await _create_user(db_session, "comment_own_private_pl")
        playlist = await _create_playlist_directly(
            db_session, owner.id, title="MyPrivatePL", is_private=True
        )

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(owner),
            json={
                "target_type": "playlist",
                "target_id": playlist.id,
                "content": "My private comment",
            },
        )
        assert resp.status_code == 201
        assert api_data(resp)["content"] == "My private comment"

    async def test_create_comment_empty_content(self, client: TestClient, db_session: AsyncSession):
        """测试发表空内容评论时返回 422。"""
        user = await _create_user(db_session, "comment_empty")
        music = await _create_music_directly(db_session)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "",
            },
        )
        assert resp.status_code == 422

    async def test_create_comment_nonexistent_parent(self, client: TestClient, db_session: AsyncSession):
        """测试回复不存在的父评论时返回 404。"""
        user = await _create_user(db_session, "comment_nx_parent")
        music = await _create_music_directly(db_session)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Reply to nothing",
                "parent_id": 99999,
            },
        )
        assert resp.status_code == 404

    async def test_create_comment_deleted_parent(self, client: TestClient, db_session: AsyncSession):
        """测试回复已删除的父评论时返回 404。"""
        user = await _create_user(db_session, "comment_del_parent")
        music = await _create_music_directly(db_session)
        parent = await _create_comment_directly(
            db_session, user.id, "Deleted", music_id=music.id, is_deleted=True
        )

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Reply to deleted",
                "parent_id": parent.id,
            },
        )
        assert resp.status_code == 404

    async def test_create_comment_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户发表评论时返回 401。"""
        music = await _create_music_directly(db_session)

        resp = client.post(
            BASE_URL + "/",
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Unauthorized",
            },
        )
        assert resp.status_code == 401


# ============================================================================
# 获取评论列表
# ============================================================================


class TestListComments:
    """测试获取评论列表相关功能。"""

    async def test_list_comments_on_music(self, client: TestClient, db_session: AsyncSession):
        """测试正常获取音乐下的评论列表。"""
        user = await _create_user(db_session, "list_comment_user")
        music = await _create_music_directly(db_session, title="SongWithComments")

        await _create_comment_directly(db_session, user.id, "Comment A", music_id=music.id)
        await _create_comment_directly(db_session, user.id, "Comment B", music_id=music.id)

        resp = client.get(f"{BASE_URL}/music/{music.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 2
        assert len(data["items"]) == 2
        contents = {c["content"] for c in data["items"]}
        assert "Comment A" in contents
        assert "Comment B" in contents
        for item in data["items"]:
            assert item["liked_by_me"] is False
            assert item["disliked_by_me"] is False

    async def test_list_comments_includes_like_status(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试评论列表返回当前用户的点赞/点踩状态。"""
        user = await _create_user(db_session, "comment_like_user")
        music = await _create_music_directly(db_session, title="SongForLikeStatus")
        comment = await _create_comment_directly(
            db_session, user.id, "Liked comment", music_id=music.id
        )
        db_session.add(CommentLike(comment_id=comment.id, user_id=user.id))
        await db_session.commit()

        resp = client.get(
            f"{BASE_URL}/music/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        item = api_data(resp)["items"][0]
        assert item["liked_by_me"] is True
        assert item["disliked_by_me"] is False

    async def test_list_comments_only_roots(self, client: TestClient, db_session: AsyncSession):
        """测试列表仅返回根评论，不含回复。"""
        user = await _create_user(db_session, "list_roots_user")
        music = await _create_music_directly(db_session)
        root = await _create_comment_directly(db_session, user.id, "Root", music_id=music.id)
        await _create_comment_directly(
            db_session, user.id, "Reply", music_id=music.id, parent_id=root.id, root_id=root.id
        )

        resp = client.get(f"{BASE_URL}/music/{music.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "Root"

    async def test_list_replies_total_ignores_unrelated_comments(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试回复列表 total 仅统计该根评论下的回复，不受其他评论影响。"""
        user = await _create_user(db_session, "replies_total_user")
        music = await _create_music_directly(db_session)
        root = await _create_comment_directly(db_session, user.id, "Root", music_id=music.id)
        await _create_comment_directly(
            db_session, user.id, "Reply 1", music_id=music.id, parent_id=root.id, root_id=root.id
        )
        await _create_comment_directly(
            db_session, user.id, "Reply 2", music_id=music.id, parent_id=root.id, root_id=root.id
        )
        await _create_comment_directly(db_session, user.id, "Other root", music_id=music.id)

        resp = client.get(f"{BASE_URL}/replies/{root.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_replies_empty_when_root_deleted(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试根评论软删除后回复列表为空且 total 为 0。"""
        user = await _create_user(db_session, "replies_deleted_root_user")
        music = await _create_music_directly(db_session)
        root = await _create_comment_directly(
            db_session, user.id, "Root", music_id=music.id, is_deleted=True
        )
        await _create_comment_directly(
            db_session, user.id, "Reply", music_id=music.id, parent_id=root.id, root_id=root.id
        )

        resp = client.get(f"{BASE_URL}/replies/{root.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_comments_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
        """测试评论列表排除已删除的评论。"""
        user = await _create_user(db_session, "list_del_user")
        music = await _create_music_directly(db_session)
        await _create_comment_directly(db_session, user.id, "Visible", music_id=music.id)
        await _create_comment_directly(
            db_session, user.id, "Deleted", music_id=music.id, is_deleted=True
        )

        resp = client.get(f"{BASE_URL}/music/{music.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "Visible"

    async def test_list_comments_empty(self, client: TestClient, db_session: AsyncSession):
        """测试无评论时返回空列表。"""
        user = await _create_user(db_session, "list_empty_user")
        music = await _create_music_directly(db_session)

        resp = client.get(f"{BASE_URL}/music/{music.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_comments_pagination(self, client: TestClient, db_session: AsyncSession):
        """测试评论列表分页功能。"""
        user = await _create_user(db_session, "list_page_user")
        music = await _create_music_directly(db_session)
        for i in range(5):
            await _create_comment_directly(db_session, user.id, f"Comment{i}", music_id=music.id)

        resp = client.get(
            f"{BASE_URL}/music/{music.id}",
            params={"limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        assert api_data(resp)["total"] == 5
        assert len(api_data(resp)["items"]) == 2

        resp = client.get(
            f"{BASE_URL}/music/{music.id}",
            params={"limit": 2, "offset": 2},
        )
        assert resp.status_code == 200
        assert len(api_data(resp)["items"]) == 2

        resp = client.get(
            f"{BASE_URL}/music/{music.id}",
            params={"limit": 2, "offset": 4},
        )
        assert resp.status_code == 200
        assert len(api_data(resp)["items"]) == 1

    async def test_list_comments_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户可正常获取评论列表（公开访问）。"""
        music = await _create_music_directly(db_session)

        resp = client.get(f"{BASE_URL}/music/{music.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 0
        assert data["items"] == []


# ============================================================================
# 删除评论
# ============================================================================


class TestDeleteComment:
    """测试删除评论相关功能。"""

    async def test_delete_comment_success(self, client: TestClient, db_session: AsyncSession):
        """测试评论作者正常删除自己的评论并同步计数。"""
        user = await _create_user(db_session, "delete_comment_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, user.id, "To delete", music_id=music.id
        )

        # 直接创建评论不会触发计数维护，手动同步以匹配删除逻辑
        music.comment_count = 1
        await db_session.commit()

        resp = client.delete(
            f"{BASE_URL}/{comment.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        # 验证软删除（identity map 缓存可能过期，重新查询）
        result = await db_session.execute(select(Comment).where(Comment.id == comment.id))
        c = result.scalar_one()
        await db_session.refresh(c)
        assert c.is_deleted is True

        # 验证计数同步
        await db_session.refresh(music)
        assert music.comment_count == 0

    async def test_delete_others_comment(self, client: TestClient, db_session: AsyncSession):
        """测试删除他人评论时返回 403。"""
        owner = await _create_user(db_session, "delete_comment_owner")
        hacker = await _create_user(db_session, "delete_comment_hacker")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, owner.id, "Protected", music_id=music.id
        )

        resp = client.delete(
            f"{BASE_URL}/{comment.id}",
            headers=_auth_header(hacker),
        )
        assert resp.status_code == 403

    async def test_delete_nonexistent_comment(self, client: TestClient, db_session: AsyncSession):
        """测试删除不存在的评论时返回 404。"""
        user = await _create_user(db_session, "delete_nx_user")

        resp = client.delete(
            f"{BASE_URL}/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_delete_comment_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户删除评论时返回 401。"""
        owner = await _create_user(db_session, "delete_unauth_owner")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, owner.id, "Unauth delete", music_id=music.id
        )

        resp = client.delete(f"{BASE_URL}/{comment.id}")
        assert resp.status_code == 401


# ============================================================================
# 点赞
# ============================================================================


class TestLikeComment:
    """测试评论点赞相关功能。"""

    async def test_like_comment_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常点赞评论。"""
        author = await _create_user(db_session, "comment_author")
        liker = await _create_user(db_session, "like_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Like me", music_id=music.id
        )

        resp = client.post(
            f"{BASE_URL}/{comment.id}/like",
            headers=_auth_header(liker),
        )
        assert resp.status_code == 201

    async def test_like_comment_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试重复点赞具有幂等性，仅生成一条记录。"""
        author = await _create_user(db_session, "comment_author_idem")
        liker = await _create_user(db_session, "like_idem_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Like idem", music_id=music.id
        )

        resp = client.post(
            f"{BASE_URL}/{comment.id}/like",
            headers=_auth_header(liker),
        )
        assert resp.status_code == 201

        resp = client.post(
            f"{BASE_URL}/{comment.id}/like",
            headers=_auth_header(liker),
        )
        assert resp.status_code == 201

        result = await db_session.execute(
            select(CommentLike).where(
                CommentLike.comment_id == comment.id,
                CommentLike.user_id == liker.id,
            )
        )
        assert len(result.scalars().all()) == 1

    async def test_like_nonexistent_comment(self, client: TestClient, db_session: AsyncSession):
        """测试点赞不存在的评论时返回 404。"""
        user = await _create_user(db_session, "like_nx_user")

        resp = client.post(
            f"{BASE_URL}/99999/like",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_like_comment_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户点赞评论时返回 401。"""
        owner = await _create_user(db_session, "like_unauth_owner")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, owner.id, "Unauth like", music_id=music.id
        )

        resp = client.post(f"{BASE_URL}/{comment.id}/like")
        assert resp.status_code == 401


class TestUnlikeComment:
    """测试取消评论点赞相关功能。"""

    async def test_unlike_comment_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常取消点赞并删除记录。"""
        author = await _create_user(db_session, "comment_author_unlike")
        liker = await _create_user(db_session, "unlike_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Unlike me", music_id=music.id
        )

        client.post(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))

        resp = client.delete(
            f"{BASE_URL}/{comment.id}/like",
            headers=_auth_header(liker),
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        result = await db_session.execute(
            select(CommentLike).where(
                CommentLike.comment_id == comment.id,
                CommentLike.user_id == liker.id,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_unlike_comment_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试未点赞时取消点赞具有幂等性，正常返回 204。"""
        user = await _create_user(db_session, "unlike_idem_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, user.id, "Never liked", music_id=music.id
        )

        resp = client.delete(
            f"{BASE_URL}/{comment.id}/like",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert api_data(resp) is None


# ============================================================================
# 点踩
# ============================================================================


class TestDislikeComment:
    """测试评论点踩相关功能。"""

    async def test_dislike_comment_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常点踩评论。"""
        author = await _create_user(db_session, "dislike_comment_author")
        disliker = await _create_user(db_session, "dislike_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Dislike me", music_id=music.id
        )

        resp = client.post(
            f"{BASE_URL}/{comment.id}/dislike",
            headers=_auth_header(disliker),
        )
        assert resp.status_code == 201

    async def test_dislike_comment_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试重复点踩具有幂等性，仅生成一条记录。"""
        author = await _create_user(db_session, "dislike_idem_author")
        disliker = await _create_user(db_session, "dislike_idem_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Dislike idem", music_id=music.id
        )

        resp = client.post(
            f"{BASE_URL}/{comment.id}/dislike",
            headers=_auth_header(disliker),
        )
        assert resp.status_code == 201

        resp = client.post(
            f"{BASE_URL}/{comment.id}/dislike",
            headers=_auth_header(disliker),
        )
        assert resp.status_code == 201

        result = await db_session.execute(
            select(CommentDislike).where(
                CommentDislike.comment_id == comment.id,
                CommentDislike.user_id == disliker.id,
            )
        )
        assert len(result.scalars().all()) == 1

    async def test_dislike_nonexistent_comment(self, client: TestClient, db_session: AsyncSession):
        """测试点踩不存在的评论时返回 404。"""
        user = await _create_user(db_session, "dislike_nx_user")

        resp = client.post(
            f"{BASE_URL}/99999/dislike",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_dislike_own_comment_rejected(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试不能点踩自己的评论。"""
        author = await _create_user(db_session, "self_disliker")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "My own", music_id=music.id
        )

        resp = client.post(
            f"{BASE_URL}/{comment.id}/dislike", headers=_auth_header(author)
        )
        assert resp.status_code == 403
        await db_session.refresh(comment)
        assert comment.dislike_count == 0

    async def test_dislike_comment_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户点踩评论时返回 401。"""
        owner = await _create_user(db_session, "dislike_unauth_owner")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, owner.id, "Unauth dislike", music_id=music.id
        )

        resp = client.post(f"{BASE_URL}/{comment.id}/dislike")
        assert resp.status_code == 401


class TestUndislikeComment:
    """测试取消评论点踩相关功能。"""

    async def test_undislike_comment_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常取消点踩并删除记录。"""
        author = await _create_user(db_session, "undislike_comment_author")
        disliker = await _create_user(db_session, "undislike_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Undislike me", music_id=music.id
        )

        client.post(f"{BASE_URL}/{comment.id}/dislike", headers=_auth_header(disliker))

        resp = client.delete(
            f"{BASE_URL}/{comment.id}/dislike",
            headers=_auth_header(disliker),
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        result = await db_session.execute(
            select(CommentDislike).where(
                CommentDislike.comment_id == comment.id,
                CommentDislike.user_id == disliker.id,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_undislike_comment_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试未点踩时取消点踩具有幂等性，正常返回 204。"""
        user = await _create_user(db_session, "undislike_idem_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, user.id, "Never disliked", music_id=music.id
        )

        resp = client.delete(
            f"{BASE_URL}/{comment.id}/dislike",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert api_data(resp) is None


# ============================================================================
# 计数维护验证
# ============================================================================


class TestCommentCountOnCreate:
    """测试发表评论时评论计数维护。"""

    async def test_create_comment_increases_music_comment_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试创建评论后音乐评论计数增加。"""
        user = await _create_user(db_session, "count_music_user")
        music = await _create_music_directly(db_session, title="CountSong")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"target_type": "music", "target_id": music.id, "content": "Nice!"},
        )
        assert resp.status_code == 201

        await db_session.refresh(music)
        assert music.comment_count == 1

    async def test_create_comment_increases_playlist_comment_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试创建评论后歌单评论计数增加。"""
        user = await _create_user(db_session, "count_pl_user")
        owner = await _create_user(db_session, "count_pl_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="CountPL")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"target_type": "playlist", "target_id": playlist.id, "content": "Nice!"},
        )
        assert resp.status_code == 201

        await db_session.refresh(playlist)
        assert playlist.comment_count == 1

    async def test_create_comment_increases_space_post_comment_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试创建评论后动态评论计数增加。"""
        user = await _create_user(db_session, "count_sp_user")
        owner = await _create_user(db_session, "count_sp_owner")
        post = await _create_space_post_directly(db_session, owner.id, content="CountPost")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"target_type": "space_post", "target_id": post.id, "content": "Nice!"},
        )
        assert resp.status_code == 201

        await db_session.refresh(post)
        assert post.comment_count == 1


class TestReplyCountOnCreate:
    """测试创建回复时父评论回复计数维护。"""

    async def test_create_reply_increases_parent_reply_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试创建回复后父评论回复计数增加。"""
        user = await _create_user(db_session, "reply_count_user")
        music = await _create_music_directly(db_session)
        root = await _create_comment_directly(
            db_session, user.id, "Root", music_id=music.id
        )

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Reply",
                "parent_id": root.id,
            },
        )
        assert resp.status_code == 201

        await db_session.refresh(root)
        assert root.reply_count == 1

    async def test_create_nested_reply_increases_parent_reply_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试创建嵌套回复后直接父评论的回复计数增加。"""
        user = await _create_user(db_session, "nested_reply_count_user")
        music = await _create_music_directly(db_session)
        root = await _create_comment_directly(
            db_session, user.id, "Root", music_id=music.id
        )
        reply = await _create_comment_directly(
            db_session, user.id, "Reply", music_id=music.id, parent_id=root.id, root_id=root.id
        )

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Nested",
                "parent_id": reply.id,
            },
        )
        assert resp.status_code == 201

        await db_session.refresh(reply)
        assert reply.reply_count == 1


class TestCommentCountOnDelete:
    """测试删除评论时评论计数维护。"""

    async def test_delete_comment_decreases_music_comment_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试删除评论后音乐评论计数减少。"""
        user = await _create_user(db_session, "del_count_user")
        music = await _create_music_directly(db_session)

        # 通过 API 创建评论（触发计数维护）
        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"target_type": "music", "target_id": music.id, "content": "To delete"},
        )
        assert resp.status_code == 201
        comment_id = api_data(resp)["id"]

        await db_session.refresh(music)
        assert music.comment_count == 1

        resp = client.delete(f"{BASE_URL}/{comment_id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert api_data(resp) is None

        await db_session.refresh(music)
        assert music.comment_count == 0

    async def test_delete_reply_decreases_parent_reply_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试删除回复后父评论回复计数减少。"""
        user = await _create_user(db_session, "del_reply_count_user")
        music = await _create_music_directly(db_session)
        root = await _create_comment_directly(
            db_session, user.id, "Root", music_id=music.id
        )

        # 通过 API 创建回复
        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={
                "target_type": "music",
                "target_id": music.id,
                "content": "Reply to delete",
                "parent_id": root.id,
            },
        )
        assert resp.status_code == 201
        reply_id = api_data(resp)["id"]

        await db_session.refresh(root)
        assert root.reply_count == 1

        resp = client.delete(f"{BASE_URL}/{reply_id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert api_data(resp) is None

        await db_session.refresh(root)
        assert root.reply_count == 0


class TestLikeCount:
    """测试点赞时评论点赞计数维护。"""

    async def test_like_comment_increases_like_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试点赞后评论点赞计数增加。"""
        author = await _create_user(db_session, "like_count_author")
        liker = await _create_user(db_session, "like_count_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Like me", music_id=music.id
        )

        resp = client.post(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))
        assert resp.status_code == 201

        await db_session.refresh(comment)
        assert comment.like_count == 1

    async def test_like_comment_idempotent_like_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试重复点赞不会导致点赞计数异常增加。"""
        author = await _create_user(db_session, "like_count_author_idem")
        liker = await _create_user(db_session, "like_count_idem_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Like idem", music_id=music.id
        )

        client.post(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))
        client.post(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))

        await db_session.refresh(comment)
        assert comment.like_count == 1

    async def test_unlike_comment_decreases_like_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试取消点赞后评论点赞计数减少。"""
        author = await _create_user(db_session, "unlike_count_author")
        liker = await _create_user(db_session, "unlike_count_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Unlike me", music_id=music.id
        )

        client.post(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))
        await db_session.refresh(comment)
        assert comment.like_count == 1

        resp = client.delete(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))
        assert resp.status_code == 200
        assert api_data(resp) is None

        await db_session.refresh(comment)
        assert comment.like_count == 0


class TestDislikeCount:
    """测试点踩时评论点踩计数维护。"""

    async def test_dislike_comment_increases_dislike_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试点踩后评论点踩计数增加。"""
        author = await _create_user(db_session, "dislike_count_author")
        disliker = await _create_user(db_session, "dislike_count_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Dislike me", music_id=music.id
        )

        resp = client.post(f"{BASE_URL}/{comment.id}/dislike", headers=_auth_header(disliker))
        assert resp.status_code == 201

        await db_session.refresh(comment)
        assert comment.dislike_count == 1

    async def test_dislike_comment_idempotent_dislike_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试重复点踩不会导致点踩计数异常增加。"""
        author = await _create_user(db_session, "dislike_count_idem_author")
        disliker = await _create_user(db_session, "dislike_count_idem_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Dislike idem", music_id=music.id
        )

        client.post(f"{BASE_URL}/{comment.id}/dislike", headers=_auth_header(disliker))
        client.post(f"{BASE_URL}/{comment.id}/dislike", headers=_auth_header(disliker))

        await db_session.refresh(comment)
        assert comment.dislike_count == 1

    async def test_undislike_comment_decreases_dislike_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试取消点踩后评论点踩计数减少。"""
        author = await _create_user(db_session, "undislike_count_author")
        disliker = await _create_user(db_session, "undislike_count_user")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "Undislike me", music_id=music.id
        )

        client.post(f"{BASE_URL}/{comment.id}/dislike", headers=_auth_header(disliker))
        await db_session.refresh(comment)
        assert comment.dislike_count == 1

        resp = client.delete(f"{BASE_URL}/{comment.id}/dislike", headers=_auth_header(disliker))
        assert resp.status_code == 200
        assert api_data(resp) is None

        await db_session.refresh(comment)
        assert comment.dislike_count == 0


# ============================================================================
# user.like_count 自动维护
# ============================================================================


class TestUserLikeCountFromComment:
    """测试评论点赞/取消时自动维护 comment.user.like_count。"""

    async def test_like_comment_increases_author_like_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试点赞评论后评论作者的 like_count 增加。"""
        author = await _create_user(db_session, "author_like")
        liker = await _create_user(db_session, "liker")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "My comment", music_id=music.id
        )

        assert author.like_count == 0

        client.post(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))
        await db_session.refresh(author)
        assert author.like_count == 1

    async def test_unlike_comment_decreases_author_like_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试取消点赞后评论作者的 like_count 减少（防负保护）。"""
        author = await _create_user(db_session, "author_unlike")
        liker = await _create_user(db_session, "unliker")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "My comment", music_id=music.id
        )

        client.post(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))
        await db_session.refresh(author)
        assert author.like_count == 1

        client.delete(f"{BASE_URL}/{comment.id}/like", headers=_auth_header(liker))
        await db_session.refresh(author)
        assert author.like_count == 0

    async def test_like_own_comment_rejected(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试不能点赞自己的评论。"""
        author = await _create_user(db_session, "self_liker")
        music = await _create_music_directly(db_session)
        comment = await _create_comment_directly(
            db_session, author.id, "My own", music_id=music.id
        )

        resp = client.post(
            f"{BASE_URL}/{comment.id}/like", headers=_auth_header(author)
        )
        assert resp.status_code == 403
        await db_session.refresh(author)
        assert author.like_count == 0


# ============================================================================
# 评论排序
# ============================================================================


class TestCommentSortBy:
    """测试评论列表排序参数。"""

    async def test_sort_by_latest(self, client: TestClient, db_session: AsyncSession):
        """测试按最新排序时评论按创建时间倒序。"""
        user = await _create_user(db_session, "sort_latest")
        music = await _create_music_directly(db_session)
        a = await _create_comment_directly(db_session, user.id, "First", music_id=music.id)
        b = await _create_comment_directly(db_session, user.id, "Second", music_id=music.id)

        resp = client.get(
            f"{BASE_URL}/music/{music.id}",
            params={"sort_by": "latest"},
        )
        assert resp.status_code == 200
        items = api_data(resp)["items"]
        # 最新的在前
        assert items[0]["content"] == "Second"
        assert items[1]["content"] == "First"

    async def test_sort_by_likes(self, client: TestClient, db_session: AsyncSession):
        """测试按最热排序时评论按点赞数倒序。"""
        user = await _create_user(db_session, "sort_likes")
        music = await _create_music_directly(db_session)
        a = await _create_comment_directly(db_session, user.id, "Low", music_id=music.id)
        b = await _create_comment_directly(db_session, user.id, "High", music_id=music.id)

        # 给 b 手动加点赞记录和计数
        from sqlalchemy import update
        db_session.add(CommentLike(comment_id=b.id, user_id=user.id))
        await db_session.execute(
            update(Comment).where(Comment.id == b.id).values(like_count=2)
        )
        await db_session.commit()

        resp = client.get(
            f"{BASE_URL}/music/{music.id}", params={"sort_by": "likes"}
        )
        assert resp.status_code == 200
        items = api_data(resp)["items"]
        # 点赞多的在前
        assert items[0]["content"] == "High"
        assert items[1]["content"] == "Low"

    async def test_sort_by_recommended_default(self, client: TestClient, db_session: AsyncSession):
        """测试默认的 recommended 排序正常返回。"""
        user = await _create_user(db_session, "sort_default")
        music = await _create_music_directly(db_session)
        await _create_comment_directly(db_session, user.id, "A", music_id=music.id)
        await _create_comment_directly(db_session, user.id, "B", music_id=music.id)

        resp = client.get(f"{BASE_URL}/music/{music.id}")
        assert resp.status_code == 200
        assert api_data(resp)["total"] == 2
