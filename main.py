import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters
)
from database import init_db, get_shop_context
from setup_flow import (
    start_setup, get_shop_name, get_delivery, get_payment,
    get_product_name, get_product_price, get_product_desc,
    more_products, cancel_setup,
    SHOP_NAME, DELIVERY, PAYMENT,
    PRODUCT_NAME, PRODUCT_PRICE, PRODUCT_DESC, MORE_PRODUCTS
)
from chat_handler import handle_customer_message

load_dotenv()

OWNER_ID = os.getenv("OWNER_TELEGRAM_ID")

# ── Tiny health server so Render sees an open port ─────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ShopBot is running!")

    def log_message(self, format, *args):
        pass  # silence default request logging

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# ── Commands ─────────────────────────────────────────────────
async def start_command(update: Update, context):
    user_id = str(update.effective_user.id)
    first_name = update.effective_user.first_name

    if user_id == OWNER_ID:
        await update.message.reply_text(
            f"👋 Welcome back, {first_name}!\n\n"
            "You are the shop owner. Here are your commands:\n\n"
            "/setup — Set up your shop\n"
            "/myshop — View your shop details\n"
            "/resetshop — Reset and start over"
        )
    else:
        await update.message.reply_text(
            f"ሰላም {first_name}! 👋\n\n"
            "Welcome! How can I help you today?\n"
            "Feel free to ask about our products, prices, or delivery."
        )

async def myshop_command(update: Update, context):
    owner_id = str(update.effective_user.id)

    if owner_id != OWNER_ID:
        return

    shop, products = get_shop_context(owner_id)

    if not shop:
        await update.message.reply_text(
            "You have not set up your shop yet.\n"
            "Type /setup to get started!"
        )
        return

    product_lines = "\n".join([
        f"  • {p[0]} — {p[1]} ETB" for p in products
    ]) if products else "  No products yet."

    await update.message.reply_text(
        f"🏪 *{shop[1]}*\n\n"
        f"🚚 Delivery: {shop[2]}\n"
        f"💳 Payment: {shop[3]}\n\n"
        f"📦 Products:\n{product_lines}\n\n"
        "Type /resetshop to update your shop info.",
        parse_mode='Markdown'
    )

async def resetshop_command(update: Update, context):
    from database import delete_shop
    owner_id = str(update.effective_user.id)

    if owner_id != OWNER_ID:
        return

    delete_shop(owner_id)
    await update.message.reply_text(
        "🗑 Your shop has been reset.\n"
        "Type /setup to set it up again."
    )

def main():
    # Initialize database
    init_db()
    print("✅ Database ready")

    # Start tiny health server in background thread so Render detects an open port
    threading.Thread(target=run_health_server, daemon=True).start()
    print("✅ Health server started")

    # Build app
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_TOKEN not found in .env file")
        return

    app = Application.builder().token(token).connect_timeout(30).read_timeout(30).write_timeout(30).build()

    # Setup conversation handler
    setup_handler = ConversationHandler(
        entry_points=[CommandHandler("setup", start_setup)],
        states={
            SHOP_NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_shop_name)],
            DELIVERY:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery)],
            PAYMENT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_payment)],
            PRODUCT_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_name)],
            PRODUCT_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_price)],
            PRODUCT_DESC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_desc)],
            MORE_PRODUCTS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, more_products)],
        },
        fallbacks=[CommandHandler("cancel", cancel_setup)]
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("myshop", myshop_command))
    app.add_handler(CommandHandler("resetshop", resetshop_command))
    app.add_handler(setup_handler)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_customer_message
    ))

    print("🤖 ShopBot is running! Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
