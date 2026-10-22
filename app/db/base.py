"""Engine + session factory. Works with SQLite (local) and PostgreSQL (production)."""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    s = get_settings()
    if s.is_sqlite:
        engine = create_engine(
            s.DATABASE_URL,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )

        # SQLite ignores FOREIGN KEY / ON DELETE CASCADE unless this pragma is on.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(s.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def db_session() -> Iterator[Session]:
    """For bot handlers: `with db_session() as db:` commits on success, rolls back on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
