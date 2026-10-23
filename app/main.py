"""Single web process: FastAPI serves the Telegram webhook, the Mini App API and static files."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update

from app.api import customer, i18n, images, orders, products, shop, webhook
from app.bot.application import build_application
from app.config import get_settings
from app.logging_conf import setup_logging
from app.services.subscription import run_expiry_cycle

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
    expiry_task = asyncio.create_task(_expiry_loop(ptb.bot))
    try:
        yield
    finally:
        expiry_task.cancel()
        await ptb.stop()
        await ptb.shutdown()


async def _expiry_loop(bot) -> None:
    """Hourly: pause expired shops, warn shops ending within 3 days. Runs in-process (no worker)."""
    await asyncio.sleep(30)  # let the webhook settle first
    while True:
        try:
            counts = await run_expiry_cycle(bot)
            if counts["expired"] or counts["warned"]:
                log.info("Expiry cycle: %s", counts)
        except Exception:
            log.exception("Expiry cycle failed")
        await asyncio.sleep(3600)


app = FastAPI(title="ShopBot", docs_url=None, redoc_url=None, lifespan=lifespan)
app.include_router(webhook.router)
app.include_router(images.router)
app.include_router(shop.router)
app.include_router(products.router)
app.include_router(customer.router)
app.include_router(orders.router)
app.include_router(i18n.router)

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
