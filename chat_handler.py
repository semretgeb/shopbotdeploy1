from telegram import Update
from telegram.ext import ContextTypes
from database import save_message, get_conversation_history, shop_exists
from claude_api import get_ai_reply

# For this MVP, the bot serves one shop owner
# The owner_id is stored in the .env file
import os
from dotenv import load_dotenv
load_dotenv()

OWNER_ID = os.getenv("OWNER_TELEGRAM_ID")

async def handle_customer_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    customer_id = str(update.effective_user.id)
    message = update.message.text

    # If the message is from the owner, ignore it here
    if customer_id == OWNER_ID:
        await update.message.reply_text(
            "👋 Hi! You are the shop owner.\n"
            "Use /setup to set up your shop\n"
            "Use /myshop to view your shop details\n"
            "Use /resetshop to reset and start over"
        )
        return

    # Check if shop is set up
    if not shop_exists(OWNER_ID):
        await update.message.reply_text(
            "This shop is not set up yet. Please check back soon!"
        )
        return

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    # Save customer message
    save_message(customer_id, OWNER_ID, "user", message)

    # Get conversation history for context
    history = get_conversation_history(customer_id, OWNER_ID)

    # Get AI reply
    reply = get_ai_reply(OWNER_ID, history)

    # Save bot reply
    save_message(customer_id, OWNER_ID, "assistant", reply)

    # Send reply to customer
    await update.message.reply_text(reply)
