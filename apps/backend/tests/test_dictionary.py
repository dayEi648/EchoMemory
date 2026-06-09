"""字典管理模块测试 —— 严格遵循 TDD：先写测试，再写实现。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.dictionary import EmotionTag, Instrument, InterestTag, Language, Style
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/dictionary"


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


async def _create_style(db: AsyncSession, name: str) -> Style:
    style = Style(name=name)
    db.add(style)
    await db.commit()
    await db.refresh(style)
    return style


async def _create_language(db: AsyncSession, name: str) -> Language:
    lang = Language(name=name)
    db.add(lang)
    await db.commit()
    await db.refresh(lang)
    return lang


# ---------------------------------------------------------------------------
# 公开接口测试
# ---------------------------------------------------------------------------

class TestListDictionaryItems:
    """测试字典项列表查询公开接口。"""

    async def test_list_styles_with_data(self, client: TestClient, db_session: AsyncSession):
        """测试正常查询风格列表并返回已有数据。"""
        await _create_style(db_session, "Rock")
        await _create_style(db_session, "Jazz")
        resp = client.get(f"{BASE_URL}/styles")
        assert resp.status_code == 200
        data = resp.json()
        names = {item["name"] for item in data}
        assert "Rock" in names
        assert "Jazz" in names

    async def test_list_languages(self, client: TestClient, db_session: AsyncSession):
        """测试正常查询语言列表并返回已有数据。"""
        await _create_language(db_session, "English")
        resp = client.get(f"{BASE_URL}/languages")
        assert resp.status_code == 200
        data = resp.json()
        names = {item["name"] for item in data}
        assert "English" in names

    async def test_list_unknown_type(self, client: TestClient):
        """测试查询不存在的字典类型时返回 400。"""
        resp = client.get(f"{BASE_URL}/unknown_type")
        assert resp.status_code == 400

    async def test_list_pagination(self, client: TestClient, db_session: AsyncSession):
        """测试字典列表的分页参数生效。"""
        for i in range(5):
            await _create_style(db_session, f"Style{i}")
        resp = client.get(f"{BASE_URL}/styles", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetDictionaryItem:
    """测试字典项详情查询公开接口。"""

    async def test_get_existing_item(self, client: TestClient, db_session: AsyncSession):
        """测试正常获取存在的字典项详情。"""
        style = await _create_style(db_session, "Blues")
        resp = client.get(f"{BASE_URL}/styles/{style.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Blues"

    async def test_get_nonexistent_item(self, client: TestClient):
        """测试获取不存在的字典项时返回 404。"""
        resp = client.get(f"{BASE_URL}/styles/999")
        assert resp.status_code == 404

    async def test_get_unknown_type(self, client: TestClient):
        """测试获取未知字典类型详情时返回 400。"""
        resp = client.get(f"{BASE_URL}/unknown_type/1")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 管理员接口测试
# ---------------------------------------------------------------------------

class TestCreateDictionaryItem:
    """测试字典项创建管理员接口。"""

    async def test_admin_create_style(self, client: TestClient, db_session: AsyncSession):
        """测试管理员正常创建风格字典项。"""
        admin = await _create_user(db_session, "admin_create", role=UserRole.ADMIN.value)
        resp = client.post(
            f"{BASE_URL}/styles",
            headers=_auth_header(admin),
            json={"name": "Pop"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Pop"
        assert "id" in data

    async def test_normal_user_cannot_create(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限创建字典项时返回 403。"""
        user = await _create_user(db_session, "normal_create")
        resp = client.post(
            f"{BASE_URL}/styles",
            headers=_auth_header(user),
            json={"name": "Metal"},
        )
        assert resp.status_code == 403

    async def test_create_duplicate_name(self, client: TestClient, db_session: AsyncSession):
        """测试创建同名字典项时返回 409。"""
        admin = await _create_user(db_session, "admin_dup", role=UserRole.ADMIN.value)
        await _create_style(db_session, "Classical")
        resp = client.post(
            f"{BASE_URL}/styles",
            headers=_auth_header(admin),
            json={"name": "Classical"},
        )
        assert resp.status_code == 409

    async def test_create_invalid_type(self, client: TestClient, db_session: AsyncSession):
        """测试创建未知字典类型时返回 400。"""
        admin = await _create_user(db_session, "admin_inv", role=UserRole.ADMIN.value)
        resp = client.post(
            f"{BASE_URL}/bad_type",
            headers=_auth_header(admin),
            json={"name": "X"},
        )
        assert resp.status_code == 400


class TestUpdateDictionaryItem:
    """测试字典项更新管理员接口。"""

    async def test_admin_update_style(self, client: TestClient, db_session: AsyncSession):
        """测试管理员正常更新风格字典项。"""
        admin = await _create_user(db_session, "admin_update", role=UserRole.ADMIN.value)
        style = await _create_style(db_session, "OldName")
        resp = client.patch(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
            json={"name": "NewName"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    async def test_normal_user_cannot_update(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限更新字典项时返回 403。"""
        user = await _create_user(db_session, "normal_update")
        style = await _create_style(db_session, "Protected")
        resp = client.patch(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(user),
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    async def test_update_nonexistent_item(self, client: TestClient, db_session: AsyncSession):
        """测试更新不存在的字典项时返回 404。"""
        admin = await _create_user(db_session, "admin_nx", role=UserRole.ADMIN.value)
        resp = client.patch(
            f"{BASE_URL}/styles/999",
            headers=_auth_header(admin),
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    async def test_update_missing_name(self, client: TestClient, db_session: AsyncSession):
        """测试更新时缺少名称字段返回 422。"""
        admin = await _create_user(db_session, "admin_no_name", role=UserRole.ADMIN.value)
        style = await _create_style(db_session, "Something")
        resp = client.patch(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
            json={},
        )
        assert resp.status_code == 422


class TestDeleteDictionaryItem:
    """测试字典项删除管理员接口。"""

    async def test_admin_delete_style(self, client: TestClient, db_session: AsyncSession):
        """测试管理员正常删除风格字典项。"""
        admin = await _create_user(db_session, "admin_del", role=UserRole.ADMIN.value)
        style = await _create_style(db_session, "ToDelete")
        resp = client.delete(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 204
        # 确认已删除（使用 select 避免 identity map 缓存）
        from sqlalchemy import select
        stmt = select(Style).where(Style.id == style.id)
        assert (await db_session.execute(stmt)).scalar_one_or_none() is None

    async def test_normal_user_cannot_delete(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限删除字典项时返回 403。"""
        user = await _create_user(db_session, "normal_del")
        style = await _create_style(db_session, "ProtectedDel")
        resp = client.delete(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 403

    async def test_delete_referenced_style_blocked(self, client: TestClient, db_session: AsyncSession):
        """测试删除已被音乐引用的字典项时返回 409。"""
        admin = await _create_user(db_session, "admin_ref", role=UserRole.ADMIN.value)
        style = await _create_style(db_session, "Referenced")
        # 创建一首引用该 style 的音乐
        music = Music(title="TestSong", style_id=style.id)
        db_session.add(music)
        await db_session.commit()

        resp = client.delete(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 409

    async def test_delete_nonexistent_item(self, client: TestClient, db_session: AsyncSession):
        """测试删除不存在的字典项时返回 404。"""
        admin = await _create_user(db_session, "admin_nxdel", role=UserRole.ADMIN.value)
        resp = client.delete(
            f"{BASE_URL}/styles/999",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 404


class TestAllDictionaryTypes:
    """验证所有支持的字典类型都能被正常操作。"""

    @pytest.mark.parametrize(
        "dtype,model",
        [
            ("styles", Style),
            ("languages", Language),
            
            ("instruments", Instrument),
            ("emotion_tags", EmotionTag),
            ("interest_tags", InterestTag),
        ],
    )
    async def test_create_and_list_each_type(
        self, client: TestClient, db_session: AsyncSession, dtype: str, model
    ):
        """测试每种字典类型都能正常创建、列表和详情查询。"""
        admin = await _create_user(db_session, f"admin_{dtype}", role=UserRole.ADMIN.value)
        # 创建
        resp = client.post(
            f"{BASE_URL}/{dtype}",
            headers=_auth_header(admin),
            json={"name": f"Test{dtype}"},
        )
        assert resp.status_code == 201
        item_id = resp.json()["id"]

        # 列表（不假设表为空，只验证刚创建的元素存在）
        resp = client.get(f"{BASE_URL}/{dtype}")
        assert resp.status_code == 200
        data = resp.json()
        names = {item["name"] for item in data}
        assert f"Test{dtype}" in names

        # 详情
        resp = client.get(f"{BASE_URL}/{dtype}/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == f"Test{dtype}"
