import time

import pytest
from jose import jwt

from echomemory_backend.core.config import settings
from echomemory_backend.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify_success(self):
        plain = "my-secret-password"
        hashed = get_password_hash(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_fails(self):
        plain = "my-secret-password"
        hashed = get_password_hash(plain)
        assert verify_password("wrong-password", hashed) is False

    def test_different_passwords_produce_different_hashes(self):
        h1 = get_password_hash("password1")
        h2 = get_password_hash("password1")
        assert h1 != h2  # bcrypt salts are random


class TestAccessToken:
    def test_create_and_decode_success(self):
        token = create_access_token(subject=42)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_decode_expired_token_returns_none(self):
        from datetime import timedelta

        token = create_access_token(subject=1, expires_delta=timedelta(seconds=-1))
        time.sleep(0.1)
        payload = decode_access_token(token)
        assert payload is None

    def test_decode_invalid_token_returns_none(self):
        payload = decode_access_token("totally.invalid.token")
        assert payload is None

    def test_decode_token_with_wrong_secret_returns_none(self):
        token = jwt.encode(
            {"sub": "1", "type": "access"},
            "wrong-secret",
            algorithm="HS256",
        )
        payload = decode_access_token(token)
        assert payload is None

    def test_decode_token_missing_type_returns_none(self):
        token = jwt.encode(
            {"sub": "1"},
            settings.secret_key,
            algorithm="HS256",
        )
        payload = decode_access_token(token)
        assert payload is None

    def test_decode_token_wrong_type_returns_none(self):
        token = jwt.encode(
            {"sub": "1", "type": "refresh"},
            settings.secret_key,
            algorithm="HS256",
        )
        payload = decode_access_token(token)
        assert payload is None
