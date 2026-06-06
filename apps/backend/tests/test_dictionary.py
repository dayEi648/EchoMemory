"""字典管理模块测试 —— 严格遵循 TDD：先写测试，再写实现。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.dictionary import City, EmotionTag, Instrument, InterestTag, Language, Style
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/dictionary"


def _create_user(
    db: Session,
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
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


def _create_style(db: Session, name: str) -> Style:
    style = Style(name=name)
    db.add(style)
    db.commit()
    db.refresh(style)
    return style


def _create_language(db: Session, name: str) -> Language:
    lang = Language(name=name)
    db.add(lang)
    db.commit()
    db.refresh(lang)
    return lang


# ---------------------------------------------------------------------------
# 公开接口测试
# ---------------------------------------------------------------------------

class TestListDictionaryItems:
    def test_list_styles_empty(self, client: TestClient):
        resp = client.get(f"{BASE_URL}/styles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_styles_with_data(self, client: TestClient, db_session: Session):
        _create_style(db_session, "Rock")
        _create_style(db_session, "Jazz")
        resp = client.get(f"{BASE_URL}/styles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {item["name"] for item in data}
        assert names == {"Rock", "Jazz"}

    def test_list_languages(self, client: TestClient, db_session: Session):
        _create_language(db_session, "English")
        resp = client.get(f"{BASE_URL}/languages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "English"

    def test_list_unknown_type(self, client: TestClient):
        resp = client.get(f"{BASE_URL}/unknown_type")
        assert resp.status_code == 400

    def test_list_pagination(self, client: TestClient, db_session: Session):
        for i in range(5):
            _create_style(db_session, f"Style{i}")
        resp = client.get(f"{BASE_URL}/styles", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetDictionaryItem:
    def test_get_existing_item(self, client: TestClient, db_session: Session):
        style = _create_style(db_session, "Blues")
        resp = client.get(f"{BASE_URL}/styles/{style.id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Blues"

    def test_get_nonexistent_item(self, client: TestClient):
        resp = client.get(f"{BASE_URL}/styles/99999")
        assert resp.status_code == 404

    def test_get_unknown_type(self, client: TestClient):
        resp = client.get(f"{BASE_URL}/unknown_type/1")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 管理员接口测试
# ---------------------------------------------------------------------------

class TestCreateDictionaryItem:
    def test_admin_create_style(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_create", role=UserRole.ADMIN.value)
        resp = client.post(
            f"{BASE_URL}/styles",
            headers=_auth_header(admin),
            json={"name": "Pop"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Pop"
        assert "id" in data

    def test_normal_user_cannot_create(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "normal_create")
        resp = client.post(
            f"{BASE_URL}/styles",
            headers=_auth_header(user),
            json={"name": "Metal"},
        )
        assert resp.status_code == 403

    def test_create_duplicate_name(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_dup", role=UserRole.ADMIN.value)
        _create_style(db_session, "Classical")
        resp = client.post(
            f"{BASE_URL}/styles",
            headers=_auth_header(admin),
            json={"name": "Classical"},
        )
        assert resp.status_code == 409

    def test_create_invalid_type(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_inv", role=UserRole.ADMIN.value)
        resp = client.post(
            f"{BASE_URL}/bad_type",
            headers=_auth_header(admin),
            json={"name": "X"},
        )
        assert resp.status_code == 400


class TestUpdateDictionaryItem:
    def test_admin_update_style(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_update", role=UserRole.ADMIN.value)
        style = _create_style(db_session, "OldName")
        resp = client.patch(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
            json={"name": "NewName"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"

    def test_normal_user_cannot_update(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "normal_update")
        style = _create_style(db_session, "Protected")
        resp = client.patch(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(user),
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403

    def test_update_nonexistent_item(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_nx", role=UserRole.ADMIN.value)
        resp = client.patch(
            f"{BASE_URL}/styles/99999",
            headers=_auth_header(admin),
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404

    def test_update_missing_name(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_no_name", role=UserRole.ADMIN.value)
        style = _create_style(db_session, "Something")
        resp = client.patch(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
            json={},
        )
        assert resp.status_code == 422


class TestDeleteDictionaryItem:
    def test_admin_delete_style(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_del", role=UserRole.ADMIN.value)
        style = _create_style(db_session, "ToDelete")
        resp = client.delete(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 204
        # 确认已删除
        assert db_session.get(Style, style.id) is None

    def test_normal_user_cannot_delete(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "normal_del")
        style = _create_style(db_session, "ProtectedDel")
        resp = client.delete(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 403

    def test_delete_referenced_style_blocked(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_ref", role=UserRole.ADMIN.value)
        style = _create_style(db_session, "Referenced")
        # 创建一首引用该 style 的音乐
        music = Music(title="TestSong", style_id=style.id)
        db_session.add(music)
        db_session.commit()

        resp = client.delete(
            f"{BASE_URL}/styles/{style.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 409

    def test_delete_nonexistent_item(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_nxdel", role=UserRole.ADMIN.value)
        resp = client.delete(
            f"{BASE_URL}/styles/99999",
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
            ("cities", City),
            ("instruments", Instrument),
            ("emotion_tags", EmotionTag),
            ("interest_tags", InterestTag),
        ],
    )
    def test_create_and_list_each_type(
        self, client: TestClient, db_session: Session, dtype: str, model
    ):
        admin = _create_user(db_session, f"admin_{dtype}", role=UserRole.ADMIN.value)
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
