import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from echomemory_backend.api.v1.router import router as api_v1_router
from echomemory_backend.core.config import settings
from echomemory_backend.models import Base  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: run Alembic migrations on startup."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config(str(base_dir / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, command.upgrade, alembic_cfg, "head")
    yield


app = FastAPI(title="echomemory backend", lifespan=lifespan)
app.include_router(api_v1_router, prefix="/api")
