from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/echomemory"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"

    class Config:
        env_file = ".env"


settings = Settings()
