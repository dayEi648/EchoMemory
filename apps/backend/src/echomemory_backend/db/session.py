from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from echomemory_backend.core.config import settings
from echomemory_backend.db.base import Base

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
