from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import save_shop, add_product, delete_shop, shop_exists

# Conversation states
SHOP_NAME, DELIVERY, PAYMENT, PAYMENT_NUMBER, PRODUCT_NAME, PRODUCT_PRICE, PRODUCT_DESC, MORE_PRODUCTS = range(8)

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
        "I will ask you a few questions to set up your shop.\n\n"
        "Let's start! 🚀\n\n"
        "*What is your shop name?*",
        parse_mode='Markdown'
    )
    return SHOP_NAME

async def get_shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['shop_name'] = update.message.text
    await update.message.reply_text(
        f"✅ Shop name: *{update.message.text}*\n\n"
        "What is your delivery information?\n"
        "_e.g. Addis Ababa only, 50 ETB fee, 1–2 days_",
        parse_mode='Markdown'
    )
    return DELIVERY

async def get_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['delivery'] = update.message.text
    await update.message.reply_text(
        "What payment methods do you accept?\n"
        "_e.g. Telebirr, CBE Birr_",
        parse_mode='Markdown'
    )
    return PAYMENT

async def get_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['payment'] = update.message.text
    await update.message.reply_text(
        "What is your payment phone number?\n"
        "_e.g. 0912345678 (Telebirr or CBE number customers will send money to)_",
        parse_mode='Markdown'
    )
    return PAYMENT_NUMBER

async def get_payment_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['payment_number'] = update.message.text
    await update.message.reply_text(
        f"✅ Payment number saved: *{update.message.text}*\n\n"
        "Now let's add your products! 📦\n\n"
        "*What is the name of your first product?*",
        parse_mode='Markdown'
    )
    return PRODUCT_NAME

async def get_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['current_product'] = {'name': update.message.text}
    await update.message.reply_text(
        f"Product: *{update.message.text}*\n\n"
        "What is the price in ETB?\n"
        "_e.g. 500 or 400–800_",
        parse_mode='Markdown'
    )
    return PRODUCT_PRICE

async def get_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['current_product']['price'] = update.message.text
    await update.message.reply_text(
        "Add a short description or type *SKIP*",
        parse_mode='Markdown'
    )
    return PRODUCT_DESC

async def get_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    if desc.upper() == 'SKIP':
        desc = ''

    owner_id = str(update.effective_user.id)
    p = context.user_data['current_product']

    if 'shop_saved' not in context.user_data:
        save_shop(
            owner_id,
            context.user_data['shop_name'],
            context.user_data['delivery'],
            context.user_data['payment'],
            context.user_data['payment_number']
        )
        context.user_data['shop_saved'] = True

    add_product(owner_id, p['name'], p['price'], desc)

    await update.message.reply_text(
        f"✅ *{p['name']}* added — {p['price']} ETB\n\n"
        "Add another product or type *DONE* to finish.",
        parse_mode='Markdown'
    )
    return MORE_PRODUCTS

async def more_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.upper() == 'DONE':
        shop_name = context.user_data.get('shop_name', 'your shop')
        await update.message.reply_text(
            f"🎉 *{shop_name}* is now live!\n\n"
            "Your AI assistant is ready to reply to customers 24/7.\n\n"
            "Commands:\n"
            "/myshop — View your shop\n"
            "/orders — View pending orders\n"
            "/resetshop — Reset shop",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END
    else:
        context.user_data['current_product'] = {'name': update.message.text}
        await update.message.reply_text(
            f"Product: *{update.message.text}*\n\nWhat is the price in ETB?",
            parse_mode='Markdown'
        )
        return PRODUCT_PRICE

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Setup cancelled. Type /setup to start again.")
    return ConversationHandler.END
