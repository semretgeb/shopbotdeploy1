"""Builds the python-telegram-bot Application in webhook mode (no Updater, no polling)."""
import logging

from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.bot import router
from app.bot.handlers import admin, assistant, onboarding, orders_owner, products, share, shop_customer, start, subscription  # noqa: F401  (registers @on_state/@on_callback)
from app.config import get_settings

log = logging.getLogger(__name__)


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
    # Commands first, then every button press, then every other private-chat message.
    app.add_handler(CommandHandler("start", start.start_command))
    app.add_handler(CommandHandler("admin", admin.admin_command))
    app.add_handler(CallbackQueryHandler(router.handle_callback))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, router.handle_message))
