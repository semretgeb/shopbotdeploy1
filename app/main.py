"""Single web process: FastAPI serves the Telegram webhook, the Mini App API and static files."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update

from app.api import images, webhook
from app.bot.application import build_application
from app.config import get_settings
from app.logging_conf import setup_logging

log = logging.getLogger(__name__)
WEBAPP_DIR = Path(__file__).parent / "webapp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.LOG_LEVEL)
    Path(s.IMAGE_CACHE_DIR).mkdir(parents=True, exist_ok=True)

    ptb = build_application()
    app.state.ptb = ptb
    await ptb.initialize()
    await ptb.bot.set_webhook(
        url=s.webhook_url,
        secret_token=s.WEBHOOK_SECRET,
        allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY],
        drop_pending_updates=s.ENV != "production",
    )
    await ptb.start()
    log.info("Webhook set to %s (env=%s, db=%s)", s.webhook_url, s.ENV, "sqlite" if s.is_sqlite else "postgres")
    try:
        yield
    finally:
        await ptb.stop()
        await ptb.shutdown()


app = FastAPI(title="ShopBot", docs_url=None, redoc_url=None, lifespan=lifespan)
app.include_router(webhook.router)
app.include_router(images.router)
# Part 3 adds: shop, products, orders, customer, i18n routers.

if WEBAPP_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled API error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"code": "internal", "message": "Internal error"})


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return {"ok": True}


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": "shopbot", "bot": f"https://t.me/{get_settings().BOT_USERNAME}"}
