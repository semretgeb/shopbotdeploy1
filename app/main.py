"""Single web process: FastAPI serves the Telegram webhook, the Mini App API and static files."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
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
    try:
        await ptb.bot.set_webhook(
            url=s.webhook_url,
            secret_token=s.WEBHOOK_SECRET,
            allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY],
            drop_pending_updates=s.ENV != "production",
        )
        log.info("Webhook set to %s (env=%s, db=%s)", s.webhook_url, s.ENV, "sqlite" if s.is_sqlite else "postgres")
    except Exception as e:  # keep the web server up so /healthz passes and the real error is visible in logs
        log.error("COULD NOT SET WEBHOOK to %s: %s — check PUBLIC_URL (must be https://<public-domain>) and BOT_TOKEN", s.webhook_url, e)
    await ptb.start()
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


@app.get("/debug/webhook", include_in_schema=False)
async def debug_webhook(request: Request, key: str = Query(...)) -> dict:
    """Diagnose why Telegram isn't delivering updates. Guarded by WEBHOOK_SECRET.

    Returns the bot's username, the webhook URL Telegram actually has registered vs the one we
    expect, pending update count, and Telegram's last_error_message so webhook/token/URL mismatches
    are obvious without SSHing into the server.
    """
    s = get_settings()
    if key != s.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")
    bot = request.app.state.ptb.bot
    try:
        me = await bot.get_me()
        info = await bot.get_webhook_info()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"telegram unreachable: {e}")
    return {
        "bot_username": me.username,
        "expected_webhook": s.webhook_url,
        "registered_webhook": info.url,
        "match": info.url == s.webhook_url,
        "pending_update_count": info.pending_update_count,
        "last_error_date": info.last_error_date.isoformat() if info.last_error_date else None,
        "last_error_message": info.last_error_message,
        "ip_address": info.ip_address,
        "max_connections": info.max_connections,
        "allowed_updates": info.allowed_updates,
        "has_custom_certificate": info.has_custom_certificate,
    }


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": "shopbot", "bot": f"https://t.me/{get_settings().BOT_USERNAME}"}
