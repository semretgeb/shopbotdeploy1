"""Telegram -> FastAPI -> python-telegram-bot (webhook mode, no polling)."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from telegram import Update

from app.config import Settings, get_settings

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> Response:
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="bad secret")
    application = request.app.state.ptb
    try:
        update = Update.de_json(await request.json(), application.bot)
    except Exception:  # malformed body — tell Telegram "ok" so it doesn't retry forever
        log.exception("Could not parse update")
        return Response(status_code=200)
    # Queue and return immediately; Application.start() runs the processing loop.
    await application.update_queue.put(update)
    return Response(status_code=200)
