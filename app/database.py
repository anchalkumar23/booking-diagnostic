"""SQLAlchemy engine/session setup and the FastAPI DB dependency."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
# check_same_thread/StaticPool only matter for the SQLite test DB; ignored by Postgres.
# StaticPool keeps a single shared connection alive so an in-memory DB survives
# across the worker threads FastAPI's sync endpoints run on.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    poolclass=StaticPool if _is_sqlite else None,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
