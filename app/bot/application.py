"""Builds the python-telegram-bot Application in webhook mode (no Updater, no polling)."""
import logging

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from app.config import get_settings

log = logging.getLogger(__name__)


async def _ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Part 1 smoke test. Replaced by the real /start in Part 2."""
    if update.effective_message:
        await update.effective_message.reply_text("ShopBot core is alive ✅")


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error while processing update %s", getattr(update, "update_id", "?"), exc_info=context.error)


def build_application() -> Application:
    s = get_settings()
    app = (
        ApplicationBuilder()
        .token(s.BOT_TOKEN)
        .updater(None)  # webhook mode: FastAPI feeds update_queue
        .concurrent_updates(True)
        .build()
    )
    register_handlers(app)
    app.add_error_handler(_on_error)
    return app


def register_handlers(app: Application) -> None:
    # Part 2+ will import handler modules here. Keep this the single registration point.
    app.add_handler(CommandHandler("ping", _ping))
    app.add_handler(CommandHandler("start", _ping))
