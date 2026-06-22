from telegram import Update
from telegram.ext import ContextTypes
from database import (save_message, get_conversation_history,
                      shop_exists, create_order, update_order_status,
                      get_shop_context)
from claude_api import get_ai_reply
import os
from dotenv import load_dotenv
load_dotenv()

OWNER_ID = os.getenv("OWNER_TELEGRAM_ID")

# Tracks which customers are waiting to send a payment screenshot
# Format: { customer_id: order_id }
pending_screenshot = {}

async def handle_customer_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    customer_id = str(update.effective_user.id)
    customer_name = update.effective_user.first_name or "Customer"

    # If owner messages the bot
    if customer_id == OWNER_ID:
        await update.message.reply_text(
            "👋 You are the shop owner.\n"
            "/setup — Set up your shop\n"
            "/myshop — View shop details\n"
            "/orders — View pending orders\n"
            "/resetshop — Reset shop"
        )
        return

    # Check if shop is set up
    if not shop_exists(OWNER_ID):
        await update.message.reply_text(
            "This shop is not set up yet. Please check back soon!"
        )
        return

    # Check if customer is supposed to send a payment screenshot
    if customer_id in pending_screenshot:
        if update.message.photo:
            order_id = pending_screenshot[customer_id]
            shop, _ = get_shop_context(OWNER_ID)

            # Update order status
            update_order_status(order_id, "pending_verification")

            # Forward screenshot to owner with approve/reject buttons
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"💰 *New Payment Screenshot!*\n\n"
                     f"👤 Customer: {customer_name} (ID: `{customer_id}`)\n"
                     f"🧾 Order ID: `{order_id}`\n\n"
                     f"To approve: `/approve {order_id}`\n"
                     f"To reject: `/reject {order_id}`",
                parse_mode='Markdown'
            )
            await context.bot.forward_message(
                chat_id=OWNER_ID,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )

            # Tell customer we received it
            await update.message.reply_text(
                "✅ Thank you! We received your payment screenshot.\n\n"
                "We will verify it shortly and confirm your order. "
                "Please wait a moment! 🙏"
            )
            del pending_screenshot[customer_id]
            return
        else:
            # They sent text instead of a screenshot
            await update.message.reply_text(
                "Please send your *payment screenshot* as a photo. 📸\n\n"
                "Take a screenshot of your Telebirr or CBE transfer and send it here.",
                parse_mode='Markdown'
            )
            return

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    message = update.message.text

    # Save customer message
    save_message(customer_id, OWNER_ID, "user", message)

    # Get conversation history
    history = get_conversation_history(customer_id, OWNER_ID)

    # Get AI reply
    reply = get_ai_reply(OWNER_ID, history)

    # Save bot reply
    save_message(customer_id, OWNER_ID, "assistant", reply)

    # Check if reply is asking for payment (simple keyword check)
    payment_keywords = ["pay", "send", "transfer", "screenshot", "receipt", "telebirr", "cbe"]
    if any(word in reply.lower() for word in payment_keywords):
        # Create a pending order
        order_id = create_order(
            customer_id, customer_name, OWNER_ID,
            "Order", "TBD", "TBD"
        )
        pending_screenshot[customer_id] = order_id

    await update.message.reply_text(reply)
