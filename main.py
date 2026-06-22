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
from database import init_db, get_shop_context, get_order, update_order_status, get_pending_orders
from setup_flow import (
    start_setup, get_shop_name, get_delivery, get_payment,
    get_payment_number, get_product_name, get_product_price,
    get_product_desc, more_products, cancel_setup,
    SHOP_NAME, DELIVERY, PAYMENT, PAYMENT_NUMBER,
    PRODUCT_NAME, PRODUCT_PRICE, PRODUCT_DESC, MORE_PRODUCTS
)
from chat_handler import handle_customer_message

load_dotenv()
OWNER_ID = os.getenv("OWNER_TELEGRAM_ID")

# ── Health server for Render ──────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ShopBot is running!")
    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

# ── Commands ──────────────────────────────────────────────────
async def start_command(update: Update, context):
    user_id = str(update.effective_user.id)
    first_name = update.effective_user.first_name
    if user_id == OWNER_ID:
        await update.message.reply_text(
            f"👋 Welcome back, {first_name}!\n\n"
            "/setup — Set up your shop\n"
            "/myshop — View shop details\n"
            "/orders — View pending orders\n"
            "/resetshop — Reset shop"
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
        await update.message.reply_text("You have not set up your shop yet.\nType /setup to get started!")
        return
    product_lines = "\n".join([f"  • {p[0]} — {p[1]} ETB" for p in products]) if products else "  No products yet."
    await update.message.reply_text(
        f"🏪 *{shop[1]}*\n\n"
        f"🚚 Delivery: {shop[2]}\n"
        f"💳 Payment: {shop[3]}\n"
        f"📱 Payment number: {shop[4]}\n\n"
        f"📦 Products:\n{product_lines}",
        parse_mode='Markdown'
    )

async def orders_command(update: Update, context):
    owner_id = str(update.effective_user.id)
    if owner_id != OWNER_ID:
        return
    orders = get_pending_orders(owner_id)
    if not orders:
        await update.message.reply_text("✅ No pending orders right now.")
        return
    msg = "📋 *Pending Orders:*\n\n"
    for o in orders:
        msg += (f"🧾 Order #{o[0]}\n"
                f"👤 {o[2]} (ID: {o[1]})\n"
                f"📦 {o[4]}\n"
                f"📍 {o[6]}\n"
                f"To approve: `/approve {o[0]}`\n"
                f"To reject: `/reject {o[0]}`\n\n")
    await update.message.reply_text(msg, parse_mode='Markdown')

async def approve_command(update: Update, context):
    owner_id = str(update.effective_user.id)
    if owner_id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve ORDER_ID")
        return
    order_id = int(context.args[0])
    order = get_order(order_id)
    if not order:
        await update.message.reply_text("Order not found.")
        return
    update_order_status(order_id, "confirmed")
    # Notify customer
    await context.bot.send_message(
        chat_id=order[1],
        text="✅ *Your payment has been verified!*\n\n"
             "Your order is confirmed and will be delivered soon. Thank you! 🙏",
        parse_mode='Markdown'
    )
    await update.message.reply_text(f"✅ Order #{order_id} approved and customer notified.")

async def reject_command(update: Update, context):
    owner_id = str(update.effective_user.id)
    if owner_id != OWNER_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /reject ORDER_ID")
        return
    order_id = int(context.args[0])
    order = get_order(order_id)
    if not order:
        await update.message.reply_text("Order not found.")
        return
    update_order_status(order_id, "rejected")
    # Notify customer
    await context.bot.send_message(
        chat_id=order[1],
        text="❌ *We could not verify your payment.*\n\n"
             "Please send a clear screenshot of your transfer or contact us for help.",
        parse_mode='Markdown'
    )
    await update.message.reply_text(f"❌ Order #{order_id} rejected and customer notified.")

async def resetshop_command(update: Update, context):
    from database import delete_shop
    owner_id = str(update.effective_user.id)
    if owner_id != OWNER_ID:
        return
    delete_shop(owner_id)
    await update.message.reply_text("🗑 Shop reset. Type /setup to set it up again.")

# ── Main ──────────────────────────────────────────────────────
def main():
    init_db()
    print("✅ Database ready")

    threading.Thread(target=run_health_server, daemon=True).start()
    print("✅ Health server started")

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("❌ TELEGRAM_TOKEN not found in .env")
        return

    app = Application.builder().token(token).connect_timeout(30).read_timeout(30).write_timeout(30).build()

    setup_handler = ConversationHandler(
        entry_points=[CommandHandler("setup", start_setup)],
        states={
            SHOP_NAME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_shop_name)],
            DELIVERY:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_delivery)],
            PAYMENT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_payment)],
            PAYMENT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_payment_number)],
            PRODUCT_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_name)],
            PRODUCT_PRICE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_price)],
            PRODUCT_DESC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_desc)],
            MORE_PRODUCTS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, more_products)],
        },
        fallbacks=[CommandHandler("cancel", cancel_setup)]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("myshop", myshop_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("reject", reject_command))
    app.add_handler(CommandHandler("resetshop", resetshop_command))
    app.add_handler(setup_handler)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_customer_message))

    print("🤖 ShopBot is running!")
    app.run_polling()

if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
