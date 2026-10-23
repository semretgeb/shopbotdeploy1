"""Shared fixtures. Tests run on a throwaway SQLite DB; no network, no Telegram."""
import os

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-abcdefghijklmnopqrstuvwxyz")
os.environ.setdefault("BOT_USERNAME", "TestShopBot")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("PUBLIC_URL", "https://example.test")
os.environ.setdefault("ADMIN_TELEGRAM_ID", "999")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_shopbot.db")
os.environ.setdefault("IMAGE_CACHE_DIR", "/tmp/shopbot-test-img")
os.environ.setdefault("ENV", "test")
os.environ["GROQ_API_KEY"] = ""  # never call Groq from tests, even if .env has a key

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base, SessionLocal, engine  # noqa: E402
import app.db.models  # noqa: E402,F401
from app.db.repo import shops as shops_repo  # noqa: E402
from app.db.repo import users as users_repo  # noqa: E402
from app.services.telegram_auth import build_init_data  # noqa: E402

BOT_TOKEN = os.environ["BOT_TOKEN"]


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture
def two_shops(db):
    """Two owners, two shops — the basis of every isolation test."""
    users_repo.upsert_tg_user(db, 1001, "owner_a", "A")
    users_repo.upsert_tg_user(db, 1002, "owner_b", "B")
    a = shops_repo.create(db, 1001, "Abebe Fashion", trial_days=14)
    b = shops_repo.create(db, 1002, "Bethel Cosmetics", trial_days=14)
    db.commit()
    return a, b


@pytest.fixture
def client():
    """FastAPI TestClient WITHOUT the Telegram lifespan (no webhook call)."""
    from app.main import app

    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c


def signed_init_data(user_id: int = 5001, start_param: str | None = None, **extra) -> str:
    import time

    fields = {"auth_date": int(time.time()), "query_id": "AAEx", "user": {"id": user_id, "first_name": "Test"}}
    if start_param:
        fields["start_param"] = start_param
    fields.update(extra)
    return build_init_data(fields, BOT_TOKEN)


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _noop_lifespan(app):
    yield
