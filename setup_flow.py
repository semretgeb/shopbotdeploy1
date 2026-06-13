from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import save_shop, add_product, delete_shop, shop_exists

# Conversation states
SHOP_NAME, DELIVERY, PAYMENT, PRODUCT_NAME, PRODUCT_PRICE, PRODUCT_DESC, MORE_PRODUCTS = range(7)

# ── Entry point ──────────────────────────────────────────────
async def start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner_id = str(update.effective_user.id)

    if shop_exists(owner_id):
        await update.message.reply_text(
            "⚠️ You already have a shop set up.\n\n"
            "Type /resetshop to start over, or /myshop to see your current shop."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Welcome to *ShopBot Setup!*\n\n"
        "I will ask you a few questions to set up your shop.\n"
        "Your customers will then be able to chat with your AI assistant 24/7.\n\n"
        "Let's start! 🚀\n\n"
        "*What is your shop name?*",
        parse_mode='Markdown'
    )
    return SHOP_NAME

# ── Shop name ────────────────────────────────────────────────
async def get_shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['shop_name'] = update.message.text
    await update.message.reply_text(
        f"✅ Shop name: *{update.message.text}*\n\n"
        "What is your delivery information?\n"
        "_e.g. Addis Ababa only, 50 ETB fee, 1–2 days_",
        parse_mode='Markdown'
    )
    return DELIVERY

# ── Delivery info ────────────────────────────────────────────
async def get_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['delivery'] = update.message.text
    await update.message.reply_text(
        f"✅ Delivery info saved.\n\n"
        "What payment methods do you accept?\n"
        "_e.g. Telebirr, CBE Birr, cash on delivery_",
        parse_mode='Markdown'
    )
    return PAYMENT

# ── Payment methods ──────────────────────────────────────────
async def get_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['payment'] = update.message.text
    context.user_data['products'] = []
    await update.message.reply_text(
        f"✅ Payment methods saved.\n\n"
        "Now let's add your products! 📦\n\n"
        "*What is the name of your first product?*",
        parse_mode='Markdown'
    )
    return PRODUCT_NAME

# ── Product name ─────────────────────────────────────────────
async def get_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['current_product'] = {'name': update.message.text}
    await update.message.reply_text(
        f"Product: *{update.message.text}*\n\n"
        "What is the price in ETB?\n"
        "_e.g. 500 or 400–800_",
        parse_mode='Markdown'
    )
    return PRODUCT_PRICE

# ── Product price ────────────────────────────────────────────
async def get_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['current_product']['price'] = update.message.text
    await update.message.reply_text(
        "Add a short description for this product.\n"
        "_e.g. Handmade, available in red and blue_\n\n"
        "Or type *SKIP* to skip.",
        parse_mode='Markdown'
    )
    return PRODUCT_DESC

# ── Product description ──────────────────────────────────────
async def get_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    if desc.upper() == 'SKIP':
        desc = ''

    owner_id = str(update.effective_user.id)
    p = context.user_data['current_product']

    # Save shop info on first product
    if 'shop_saved' not in context.user_data:
        save_shop(
            owner_id,
            context.user_data['shop_name'],
            context.user_data['delivery'],
            context.user_data['payment']
        )
        context.user_data['shop_saved'] = True

    add_product(owner_id, p['name'], p['price'], desc)

    await update.message.reply_text(
        f"✅ *{p['name']}* added — {p['price']} ETB\n\n"
        "Do you want to add another product?\n"
        "Type the next product name or type *DONE* to finish.",
        parse_mode='Markdown'
    )
    return MORE_PRODUCTS

# ── More products or done ────────────────────────────────────
async def more_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.upper() == 'DONE':
        shop_name = context.user_data.get('shop_name', 'your shop')
        await update.message.reply_text(
            f"🎉 *{shop_name}* is now live!\n\n"
            "Your AI assistant is ready to reply to customers 24/7 "
            "in Amharic and English.\n\n"
            "Share this bot link with your customers and they can start chatting right away!\n\n"
            "Commands you can use:\n"
            "/myshop — view your shop details\n"
            "/resetshop — start setup again",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END
    else:
        context.user_data['current_product'] = {'name': update.message.text}
        await update.message.reply_text(
            f"Product: *{update.message.text}*\n\n"
            "What is the price in ETB?\n"
            "_e.g. 500 or 400–800_",
            parse_mode='Markdown'
        )
        return PRODUCT_PRICE

# ── Cancel setup ─────────────────────────────────────────────
async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Setup cancelled. Type /setup to start again anytime."
    )
    return ConversationHandler.END
