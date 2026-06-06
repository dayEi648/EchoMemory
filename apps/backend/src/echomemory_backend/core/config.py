from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env to the backend project root (where pyproject.toml lives)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    # OSS (Aliyun Object Storage Service)
    oss_access_key_id: str | None = None
    oss_access_key_secret: str | None = None
    oss_endpoint: str | None = None
    oss_bucket_name: str | None = None
    oss_avatar_prefix: str = "avatars"

    model_config = SettingsConfigDict(env_file=str(_DEFAULT_ENV_FILE))


settings = Settings()
