from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 将 .env 文件定位到后端项目根目录（pyproject.toml 所在位置）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    """从环境变量与 .env 文件加载的应用配置。"""

    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    # OSS（阿里云对象存储服务）
    oss_access_key_id: str | None = None
    oss_access_key_secret: str | None = None
    oss_endpoint: str | None = None
    oss_bucket_name: str | None = None
    oss_avatar_prefix: str = "avatars"

    model_config = SettingsConfigDict(env_file=str(_DEFAULT_ENV_FILE))


settings = Settings()
