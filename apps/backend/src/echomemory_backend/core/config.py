"""应用配置模块，从环境变量与 .env 文件加载全局设置。"""

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

    # LLM（DeepSeek）
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_pro_model: str = "deepseek-v4-pro"
    deepseek_flash_model: str = "deepseek-v4-flash"

    # DeepSeek 调用默认参数
    deepseek_default_temperature: float = 0.6
    deepseek_default_timeout: float = 60.0
    deepseek_reasoning_effort: str = "high"
    deepseek_thinking_type: str = "enabled"

    model_config = SettingsConfigDict(env_file=str(_DEFAULT_ENV_FILE))

    @property
    def async_database_url(self) -> str:
        """返回适配 asyncpg 的异步数据库连接 URL。"""
        url = self.database_url
        if "postgresql+psycopg2" in url:
            return url.replace("postgresql+psycopg2", "postgresql+asyncpg")
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
