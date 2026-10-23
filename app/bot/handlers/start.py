"""/start, deep links, language picker, owner home, shop settings, customer shop home (stub)."""
import re

from telegram import Update
from telegram.ext import ContextTypes

from app.bot import states as S
from app.bot.context import Ctx, build_ctx
from app.bot.keyboards import Btn, cancel_only, kb, lang_picker, nav_row, web_app_button
from app.bot.router import arg, on_callback, on_state, set_fallback
from app.config import get_settings
from app.db.base import db_session
from app.db.repo import orders as orders_repo
from app.db.repo import products as products_repo
from app.db.repo import shops as shops_repo
from app.db.repo import users as users_repo
from app.services import subscription as sub
from app.services.qr import shop_link

SLUG_RE = re.compile(r"^[a-z0-9-]{3,48}$")


# --- /start -----------------------------------------------------------------

async def start_command(update: Update, tg: ContextTypes.DEFAULT_TYPE) -> None:
    with db_session() as db:
        ctx = build_ctx(update, tg, db)
        param = (tg.args[0].strip().lower() if tg.args else "")
        if param and SLUG_RE.match(param):
            await open_shop_as_customer(ctx, param)
            return
        if ctx.data.get("lang_pending"):
            await ctx.send(ctx.t("lang.pick"), lang_picker())
            return
        await show_entry(ctx)


async def show_entry(ctx: Ctx) -> None:
    """Owner -> home (or resume onboarding). Everyone else -> welcome with role choice."""
    if ctx.owner_shop:
        if not ctx.owner_shop.onboarding_done:
            from app.bot.handlers.onboarding import resume_onboarding
            await resume_onboarding(ctx)
        else:
            await owner_home(ctx)
        return
    ctx.reset()
    await ctx.render(
        ctx.t("start.welcome"),
        kb([
            [Btn(ctx.t("start.create_shop"), callback_data="onb:start")],
            [Btn(ctx.t("start.im_customer"), callback_data="start:customer")],
            [Btn(ctx.t("btn.language"), callback_data="lang:pick")],
        ]),
    )


@on_callback("start")
async def start_cb(ctx: Ctx) -> None:
    await ctx.answer()
    if arg(ctx, 1) == "customer":
        await ctx.render(ctx.t("start.customer_hint", bot=get_settings().BOT_USERNAME), kb([nav_row(ctx.lang, home=True)]))


# --- language ---------------------------------------------------------------

@on_callback("lang")
async def lang_cb(ctx: Ctx) -> None:
    choice = arg(ctx, 1)
    if choice == "pick":
        await ctx.answer()
        await ctx.render(ctx.t("lang.pick"), lang_picker())
        return
    if choice in ("am", "en"):
        users_repo.set_lang(ctx.db, ctx.user.id, choice)
        ctx.user.lang = choice
        data = ctx.data
        data.pop("lang_pending", None)
        ctx.set_state(ctx.state.state, data)
        await ctx.answer(ctx.t("lang.saved"))
        # Customer inside a shop goes back to that shop; everyone else to entry.
        if ctx.state.shop_id and not ctx.owner_shop:
            shop = shops_repo.get(ctx.db, ctx.state.shop_id)
            if shop:
                await customer_home(ctx, shop)
                return
        await show_entry(ctx)


# --- owner home -------------------------------------------------------------

async def owner_home(ctx: Ctx) -> None:
    shop = ctx.owner_shop
    if shop is None:
        await show_entry(ctx)
        return
    ctx.reset()
    s = get_settings()
    if not sub.is_shop_open(shop):
        await ctx.render(
            ctx.t("paused.owner", price=s.SUBSCRIPTION_PRICE_ETB, account=s.PAYMENT_ACCOUNT),
            kb([[Btn(ctx.t("home.subscription"), callback_data="subs:show")], [Btn(ctx.t("btn.language"), callback_data="lang:pick")]]),
        )
        return
    n_products = products_repo.count(ctx.db, shop.id)
    n_new = orders_repo.count_by_status(ctx.db, shop.id, "pending")
    days = sub.days_left(shop)
    status = ctx.t("home.status_trial", days=days) if shop.status == "trial" else ctx.t("home.status_active", days=days)
    text = ctx.t("home.title", shop=shop.name, products=n_products, orders=n_new, status=status)
    rows = [
        [Btn(ctx.t("home.add_product"), callback_data="prod:add"), Btn(ctx.t("home.products", n=n_products), callback_data="prod:list:0")],
        [Btn(ctx.t("home.orders", n=n_new), callback_data="ord:list:pending:0"), Btn(ctx.t("home.share"), callback_data="share:show")],
        [Btn(ctx.t("home.settings"), callback_data="settings:show"), Btn(ctx.t("home.subscription"), callback_data="subs:show")],
        [Btn(ctx.t("btn.language"), callback_data="lang:pick")],
    ]
    await ctx.render(text, kb(rows))


@on_callback("home")
async def home_cb(ctx: Ctx) -> None:
    await ctx.answer()
    if ctx.owner_shop:
        await owner_home(ctx)
    elif ctx.state.shop_id:
        shop = shops_repo.get(ctx.db, ctx.state.shop_id)
        if shop:
            await customer_home(ctx, shop)
            return
        await show_entry(ctx)
    else:
        await show_entry(ctx)


@on_callback("cancel")
async def cancel_cb(ctx: Ctx) -> None:
    await ctx.answer(ctx.t("err.cancelled"))
    await home_cb(ctx)


@on_callback("noop")
async def noop_cb(ctx: Ctx) -> None:
    await ctx.answer()


# --- shop settings ----------------------------------------------------------

SETTINGS_FIELDS = {
    "name": ("settings.edit_name", 80),
    "description": ("settings.edit_desc", 300),
    "phone": ("settings.edit_phone", 32),
    "delivery_info": ("settings.edit_delivery", 500),
    "payment_info": ("settings.edit_payment", 500),
}


async def settings_show(ctx: Ctx) -> None:
    shop = ctx.owner_shop
    ns = ctx.t("not_set")
    text = ctx.t(
        "settings.title",
        name=shop.name,
        desc=shop.description or ns,
        phone=shop.phone or ns,
        delivery=shop.delivery_info or ns,
        payment=shop.payment_info or ns,
    )
    rows = [
        [Btn(ctx.t("settings.edit_name"), callback_data="settings:edit:name"), Btn(ctx.t("settings.edit_desc"), callback_data="settings:edit:description")],
        [Btn(ctx.t("settings.edit_phone"), callback_data="settings:edit:phone"), Btn(ctx.t("settings.edit_delivery"), callback_data="settings:edit:delivery_info")],
        [Btn(ctx.t("settings.edit_payment"), callback_data="settings:edit:payment_info")],
        [Btn(ctx.t("settings.ai_on" if shop.ai_enabled else "settings.ai_off"), callback_data="settings:ai")],
        nav_row(ctx.lang),
    ]
    await ctx.render(text, kb(rows))


@on_callback("settings")
async def settings_cb(ctx: Ctx) -> None:
    await ctx.answer()
    if not ctx.owner_shop:
        return
    action = arg(ctx, 1)
    if action == "show":
        await settings_show(ctx)
    elif action == "ai":
        ctx.owner_shop.ai_enabled = not ctx.owner_shop.ai_enabled
        ctx.db.flush()
        await settings_show(ctx)
    elif action == "edit":
        fld = arg(ctx, 2)
        if fld in SETTINGS_FIELDS:
            ctx.set_state(S.SETTINGS_EDIT, {"field": fld})
            label = ctx.t(SETTINGS_FIELDS[fld][0])
            await ctx.render(f"{label}\n\n{ctx.t('settings.prompt')}", cancel_only(ctx.lang))


@on_state(S.SETTINGS_EDIT)
async def settings_edit_input(ctx: Ctx) -> None:
    fld = ctx.data.get("field")
    if not ctx.owner_shop or fld not in SETTINGS_FIELDS:
        ctx.reset()
        return
    value = ctx.text
    if ctx.msg.contact and fld == "phone":
        value = ctx.msg.contact.phone_number
    maxlen = SETTINGS_FIELDS[fld][1]
    if not value or len(value) > maxlen:
        await ctx.send(ctx.t("settings.prompt"), cancel_only(ctx.lang))
        return
    setattr(ctx.owner_shop, fld, value)
    ctx.db.flush()
    ctx.reset()
    await ctx.send(ctx.t("settings.updated"))
    await settings_show(ctx)


# --- customer entry (full flow arrives in Part 5) ----------------------------

async def open_shop_as_customer(ctx: Ctx, slug: str) -> None:
    shop = shops_repo.get_by_slug(ctx.db, slug)
    if shop is None:
        await ctx.send(ctx.t("start.unknown_shop"))
        return
    if ctx.owner_shop and ctx.owner_shop.id == shop.id:
        await owner_home(ctx)
        return
    lang_pending = ctx.data.get("lang_pending", False)
    ctx.set_state(S.IDLE, {"lang_pending": True} if lang_pending else {}, shop_id=shop.id)
    if not sub.is_shop_open(shop):
        await ctx.send(ctx.t("start.shop_closed", shop=shop.name))
        return
    if lang_pending:
        await ctx.send(ctx.t("lang.pick"), lang_picker())
        return
    await customer_home(ctx, shop)


async def customer_home(ctx: Ctx, shop) -> None:
    s = get_settings()
    ns = ctx.t("not_set")
    text = ctx.t("customer.home", shop=shop.name, desc=shop.description or "", phone=shop.phone or ns, delivery=shop.delivery_info or ns)
    rows = [
        [web_app_button(ctx.t("customer.open_shop"), f"{s.webapp_url}?shop={shop.slug}")],
        [Btn(ctx.t("customer.browse"), callback_data=f"cust:browse:0"), Btn(ctx.t("customer.my_orders"), callback_data="cust:orders")],
        [Btn(ctx.t("customer.ask"), callback_data="cust:ask"), Btn(ctx.t("customer.contact"), callback_data="cust:contact")],
        [Btn(ctx.t("btn.language"), callback_data="lang:pick")],
    ]
    await ctx.render(text, kb(rows))


# --- free text with no active state ----------------------------------------

@set_fallback
async def idle_text(ctx: Ctx) -> None:
    if ctx.owner_shop:
        # Owner sent a photo while idle: treat it as "add product" (photo-first shortcut).
        if ctx.msg.photo:
            from app.bot.handlers.products import start_add_with_photo
            await start_add_with_photo(ctx)
            return
        await owner_home(ctx)
        return
    if ctx.state.shop_id:
        shop = shops_repo.get(ctx.db, ctx.state.shop_id)
        if shop and sub.is_shop_open(shop):
            if ctx.msg.photo:
                from app.bot.handlers.shop_customer import photo_while_idle
                if await photo_while_idle(ctx, shop):
                    return
            if ctx.text:
                from app.bot.handlers.assistant import answer_customer
                await answer_customer(ctx, shop, ctx.text)
                return
            await customer_home(ctx, shop)
            return
    await show_entry(ctx)


def link_for(shop) -> str:
    return shop_link(get_settings().BOT_USERNAME, shop.slug)
