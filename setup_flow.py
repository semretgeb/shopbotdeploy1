from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

    context.user_data.clear()
    await update.message.reply_text(
        "👋 Welcome to *ShopBot Setup!*\n\n"
        "I will ask you a few questions to set up your shop.\n\n"
        "Let's start! 🚀\n\n"
        "*What is your shop name?*",
        parse_mode='Markdown'
    )
    return SHOP_NAME

async def get_shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['shop_name'] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Shop name: *{update.message.text.strip()}*\n\n"
        "What is your delivery information?\n"
        "_e.g. Addis Ababa only, 50 ETB fee, 1–2 days_",
        parse_mode='Markdown'
    )
    return DELIVERY

async def get_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['delivery'] = update.message.text.strip()
    await update.message.reply_text(
        "What payment methods do you accept?\n"
        "_e.g. Telebirr, CBE Birr_",
        parse_mode='Markdown'
    )
    return PAYMENT

async def get_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['payment'] = update.message.text.strip()
    await update.message.reply_text(
        "What is your payment phone number?\n"
        "_e.g. 0912345678 — customers will send money to this number_",
        parse_mode='Markdown'
    )
    return PAYMENT_NUMBER

async def get_payment_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['payment_number'] = update.message.text.strip()
    context.user_data['shop_saved'] = False
    await update.message.reply_text(
        f"✅ Payment number saved: *{update.message.text.strip()}*\n\n"
        "Now let's add your products! 📦\n\n"
        "*What is the name of your first product?*",
        parse_mode='Markdown'
    )
    return PRODUCT_NAME

async def get_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['current_product'] = {'name': name}
    await update.message.reply_text(
        f"Product: *{name}*\n\n"
        "What is the price in ETB?\n"
        "_e.g. 500 or 400–800_",
        parse_mode='Markdown'
    )
    return PRODUCT_PRICE

async def get_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = update.message.text.strip()
    context.user_data['current_product']['price'] = price

    # Show SKIP button so user doesn't have to type it
    keyboard = [['SKIP']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Add a short description or press *SKIP*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return PRODUCT_DESC

async def get_product_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc.upper() == 'SKIP':
        desc = ''

    owner_id = str(update.effective_user.id)
    p = context.user_data.get('current_product', {})

    if not p.get('name') or not p.get('price'):
        await update.message.reply_text("Something went wrong. Type /cancel and try /setup again.")
        return ConversationHandler.END

    # Save shop info on first product
    if not context.user_data.get('shop_saved'):
        save_shop(
            owner_id,
            context.user_data['shop_name'],
            context.user_data['delivery'],
            context.user_data['payment'],
            context.user_data['payment_number']
        )
        context.user_data['shop_saved'] = True

    add_product(owner_id, p['name'], p['price'], desc)

    # Show DONE button for convenience
    keyboard = [['DONE']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        f"✅ *{p['name']}* added — {p['price']} ETB\n\n"
        "Type the next product name to add another,\n"
        "or press *DONE* to finish.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return MORE_PRODUCTS

async def more_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text.upper() == 'DONE':
        shop_name = context.user_data.get('shop_name', 'your shop')
        context.user_data.clear()
        await update.message.reply_text(
            f"🎉 *{shop_name}* is now live!\n\n"
            "Your AI assistant is ready to reply to customers 24/7 "
            "in Amharic and English.\n\n"
            "Commands:\n"
            "/myshop — View your shop details\n"
            "/orders — View pending orders\n"
            "/resetshop — Reset and start over",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    else:
        # Anything that is not DONE = new product name
        context.user_data['current_product'] = {'name': text}
        await update.message.reply_text(
            f"Product: *{text}*\n\n"
            "What is the price in ETB?\n"
            "_e.g. 500 or 400–800_",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return PRODUCT_PRICE

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Setup cancelled. Type /setup to start again anytime.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END
