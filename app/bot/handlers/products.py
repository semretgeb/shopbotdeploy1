"""Product management in chat: add (photo first), list, view, edit, delete, hide/show."""
import re
from typing import Optional

from app.bot import states as S
from app.bot.context import Ctx
from app.bot.keyboards import Btn, cancel_only, kb, nav_row, paginator, skip_cancel
from app.bot.router import arg, on_callback, on_state
from app.db.models import Product
from app.db.repo import products as repo
from app.services.money import fmt_price, parse_price

# "Red Shoes - 1200", "ቀይ ጫማ – 1,200 ብር", "Shoes: 1200"
CAPTION_RE = re.compile(r"^(?P<name>.{2,80}?)\s*[-–—:]\s*(?P<price>[0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:etb|birr|ብር)?\s*$", re.I)


# --- formatting ---------------------------------------------------------------

def stock_label(ctx: Ctx, stock: Optional[int]) -> str:
    if stock is None:
        return ctx.t("prod.stock_label_unlimited")
    if stock <= 0:
        return ctx.t("prod.stock_label_out")
    return ctx.t("prod.stock_label_n", n=stock)


def category_label(ctx: Ctx, category_id: Optional[int]) -> str:
    if category_id:
        cat = repo.get_category(ctx.db, ctx.owner_shop.id, category_id)
        if cat:
            return cat.name
    return ctx.t("prod.category_none")


def product_caption(ctx: Ctx, p: Product) -> str:
    hidden = "" if p.is_active else ctx.t("prod.hidden_badge")
    return ctx.t(
        "prod.card",
        name=p.name + hidden,
        price=fmt_price(p.price_santim, ctx.lang),
        stock=stock_label(ctx, p.stock),
        category=category_label(ctx, p.category_id),
        desc=p.description or "",
    ).rstrip()


def product_card_kb(ctx: Ctx, p: Product, page: int):
    e = f"prod:edit:{p.id}"
    return kb([
        [Btn(ctx.t("prod.edit_name"), callback_data=f"{e}:name"), Btn(ctx.t("prod.edit_price"), callback_data=f"{e}:price")],
        [Btn(ctx.t("prod.edit_stock"), callback_data=f"{e}:stock"), Btn(ctx.t("prod.edit_photo"), callback_data=f"{e}:photo")],
        [Btn(ctx.t("prod.edit_category"), callback_data=f"{e}:category"), Btn(ctx.t("prod.edit_desc"), callback_data=f"{e}:description")],
        [
            Btn(ctx.t("prod.toggle_active" if p.is_active else "prod.toggle_inactive"), callback_data=f"prod:toggle:{p.id}:{page}"),
            Btn(ctx.t("btn.delete"), callback_data=f"prod:del:{p.id}:{page}"),
        ],
        nav_row(ctx.lang, back=f"prod:list:{page}"),
    ])


# --- list / view -------------------------------------------------------------

async def show_list(ctx: Ctx, page: int = 0) -> None:
    shop_id = ctx.owner_shop.id
    items, total = repo.list_page(ctx.db, shop_id, page=page, page_size=repo.PAGE_SIZE_CHAT)
    if total == 0:
        await ctx.render(ctx.t("prod.list_empty"), kb([[Btn(ctx.t("home.add_product"), callback_data="prod:add")], nav_row(ctx.lang)]))
        return
    if not items and page > 0:  # page vanished after a delete
        await show_list(ctx, page - 1)
        return
    rows = []
    for p in items:
        label = f"{'' if p.is_active else '👁 '}{p.name} · {fmt_price(p.price_santim, ctx.lang)}"
        rows.append([Btn(label[:60], callback_data=f"prod:view:{p.id}:{page}")])
    rows.append(paginator(ctx.lang, "prod", page, total, repo.PAGE_SIZE_CHAT))
    rows.append([Btn(ctx.t("home.add_product"), callback_data="prod:add")])
    rows.append(nav_row(ctx.lang))
    await ctx.render(ctx.t("prod.list_title", n=total), kb(rows))


async def show_card(ctx: Ctx, p: Product, page: int) -> None:
    caption = product_caption(ctx, p)
    markup = product_card_kb(ctx, p, page)
    if p.photo_file_id:
        await ctx.edit_photo_card(p.photo_file_id, caption, markup)
    else:
        await ctx.render(caption, markup)


@on_callback("prod")
async def prod_cb(ctx: Ctx) -> None:
    if not ctx.owner_shop:
        await ctx.answer()
        return
    action = arg(ctx, 1)
    shop_id = ctx.owner_shop.id

    if action == "add":
        await ctx.answer()
        ctx.set_state(S.PROD_PHOTO, {})
        await ctx.render(ctx.t("prod.send_photo"), cancel_only(ctx.lang))
        return

    if action in ("list", "page"):
        await ctx.answer()
        ctx.reset()
        await show_list(ctx, int(arg(ctx, 2, "0")))
        return

    pid = int(arg(ctx, 2, "0"))
    page = int(arg(ctx, 3, "0") or 0) if action != "edit" else 0
    p = repo.get(ctx.db, shop_id, pid)
    if p is None:
        await ctx.answer(ctx.t("prod.not_found"), alert=True)
        await show_list(ctx, 0)
        return

    if action == "view":
        await ctx.answer()
        await show_card(ctx, p, page)
    elif action == "toggle":
        p.is_active = not p.is_active
        ctx.db.flush()
        await ctx.answer(ctx.t("prod.updated"))
        await show_card(ctx, p, page)
    elif action == "del":
        await ctx.answer()
        await ctx.render(
            ctx.t("prod.delete_confirm", name=p.name),
            kb([[Btn(ctx.t("btn.yes"), callback_data=f"prod:delok:{p.id}:{page}"), Btn(ctx.t("btn.no"), callback_data=f"prod:view:{p.id}:{page}")]]),
        )
    elif action == "delok":
        repo.delete(ctx.db, shop_id, pid)
        await ctx.answer(ctx.t("prod.deleted"))
        await show_list(ctx, page)
    elif action == "edit":
        fld = arg(ctx, 3)
        await ctx.answer()
        await begin_edit(ctx, p, fld)
    elif action == "cat":  # category picked while editing: prod:cat:<pid>:<cat_id|0|new>
        await ctx.answer()
        choice = arg(ctx, 3)
        if choice == "new":
            ctx.set_state(S.PROD_EDIT_FIELD, {"product_id": p.id, "field": "category_new"})
            await ctx.render(ctx.t("prod.category_name"), cancel_only(ctx.lang))
            return
        p.category_id = int(choice) or None
        ctx.db.flush()
        ctx.reset()
        await show_card(ctx, p, 0)


# --- add wizard ----------------------------------------------------------------

async def start_add_with_photo(ctx: Ctx) -> None:
    """Owner sent a photo while idle -> jump straight into the wizard."""
    ctx.set_state(S.PROD_PHOTO, {})
    await prod_photo(ctx)


def _parse_caption(text: str) -> Optional[tuple[str, int]]:
    m = CAPTION_RE.match(text or "")
    if not m:
        return None
    price = parse_price(m.group("price"))
    return (m.group("name").strip(), price) if price else None


@on_state(S.PROD_PHOTO)
async def prod_photo(ctx: Ctx) -> None:
    if not ctx.msg.photo:
        await ctx.send(ctx.t("prod.need_photo"), cancel_only(ctx.lang))
        return
    photo = ctx.msg.photo[-1]
    ctx.update_data(photo_file_id=photo.file_id, photo_unique_id=photo.file_unique_id)
    parsed = _parse_caption(ctx.msg.caption or "")
    if parsed:
        name, price = parsed
        ctx.update_data(name=name, price_santim=price)
        await ask_stock(ctx)
    else:
        ctx.set_state(S.PROD_NAME, ctx.data)
        await ctx.send(ctx.t("prod.name"), cancel_only(ctx.lang))


@on_state(S.PROD_NAME)
async def prod_name(ctx: Ctx) -> None:
    name = ctx.text
    if not 2 <= len(name) <= 80:
        await ctx.send(ctx.t("prod.name_invalid"))
        return
    ctx.update_data(name=name)
    ctx.set_state(S.PROD_PRICE, ctx.data)
    await ctx.send(ctx.t("prod.price"), cancel_only(ctx.lang))


@on_state(S.PROD_PRICE)
async def prod_price(ctx: Ctx) -> None:
    price = parse_price(ctx.text)
    if price is None:
        await ctx.send(ctx.t("prod.price_invalid"))
        return
    ctx.update_data(price_santim=price)
    await ask_stock(ctx)


async def ask_stock(ctx: Ctx) -> None:
    ctx.set_state(S.PROD_STOCK, ctx.data)
    await ctx.send(
        ctx.t("prod.stock"),
        kb([[Btn(ctx.t("prod.stock_unlimited"), callback_data="prodw:unlimited")], [Btn(ctx.t("btn.cancel"), callback_data="cancel")]]),
    )


@on_state(S.PROD_STOCK)
async def prod_stock(ctx: Ctx) -> None:
    if not ctx.text.isdigit():
        await ctx.send(ctx.t("prod.stock_invalid"))
        return
    ctx.update_data(stock=int(ctx.text))
    await ask_category(ctx)


async def ask_category(ctx: Ctx) -> None:
    ctx.set_state(S.PROD_CATEGORY, ctx.data)
    cats = repo.list_categories(ctx.db, ctx.owner_shop.id)
    rows = [[Btn(c.name, callback_data=f"prodw:cat:{c.id}")] for c in cats[:20]]
    rows.append([Btn(ctx.t("prod.category_new"), callback_data="prodw:cat:new"), Btn(ctx.t("btn.skip"), callback_data="skip")])
    rows.append([Btn(ctx.t("btn.cancel"), callback_data="cancel")])
    await ctx.send(ctx.t("prod.category"), kb(rows))


@on_state(S.PROD_CATEGORY_NEW)
async def prod_category_new(ctx: Ctx) -> None:
    name = ctx.text
    if not 2 <= len(name) <= 48:
        await ctx.send(ctx.t("prod.category_invalid"))
        return
    cat = repo.get_or_create_category(ctx.db, ctx.owner_shop.id, name)
    ctx.update_data(category_id=cat.id)
    await show_preview(ctx)


@on_state(S.PROD_CATEGORY)
async def prod_category_text(ctx: Ctx) -> None:
    # Typing a category name instead of tapping is fine too.
    await prod_category_new(ctx)


async def show_preview(ctx: Ctx) -> None:
    d = ctx.data
    ctx.set_state(S.PROD_PREVIEW, d)
    text = ctx.t(
        "prod.preview",
        name=d.get("name", ""),
        price=fmt_price(int(d.get("price_santim", 0)), ctx.lang),
        stock=stock_label(ctx, d.get("stock")),
        category=category_label(ctx, d.get("category_id")),
    )
    markup = kb([[Btn(ctx.t("btn.save"), callback_data="prodw:save"), Btn(ctx.t("btn.cancel"), callback_data="cancel")]])
    await ctx.send_photo(d["photo_file_id"], text, markup)


@on_state(S.PROD_PREVIEW)
async def prod_preview_text(ctx: Ctx) -> None:
    await show_preview(ctx)


async def skip_in_product_wizard(ctx: Ctx) -> None:
    st = ctx.state.state
    if st == S.PROD_CATEGORY:
        ctx.update_data(category_id=None)
        await show_preview(ctx)
    elif st == S.PROD_EDIT_FIELD and ctx.data.get("field") == "description":
        p = repo.update(ctx.db, ctx.owner_shop.id, int(ctx.data["product_id"]), description=None)
        ctx.reset()
        if p:
            await show_card(ctx, p, 0)


@on_callback("prodw")
async def prod_wizard_cb(ctx: Ctx) -> None:
    """Buttons inside the add-product wizard."""
    if not ctx.owner_shop:
        await ctx.answer()
        return
    action = arg(ctx, 1)
    st = ctx.state.state
    if action == "unlimited" and st == S.PROD_STOCK:
        await ctx.answer()
        ctx.update_data(stock=None)
        await ask_category(ctx)
    elif action == "cat" and st == S.PROD_CATEGORY:
        await ctx.answer()
        choice = arg(ctx, 2)
        if choice == "new":
            ctx.set_state(S.PROD_CATEGORY_NEW, ctx.data)
            await ctx.send(ctx.t("prod.category_name"), cancel_only(ctx.lang))
        else:
            ctx.update_data(category_id=int(choice))
            await show_preview(ctx)
    elif action == "edit_unlimited" and st == S.PROD_EDIT_FIELD:
        await edit_unlimited(ctx)
    elif action == "save" and st == S.PROD_PREVIEW:
        d = ctx.data
        p = repo.create(
            ctx.db, ctx.owner_shop.id,
            name=d["name"], price_santim=int(d["price_santim"]), stock=d.get("stock"),
            photo_file_id=d.get("photo_file_id"), photo_unique_id=d.get("photo_unique_id"),
            category_id=d.get("category_id"),
        )
        ctx.reset()
        await ctx.answer(ctx.t("prod.saved", name=p.name))
        await ctx.render(
            ctx.t("prod.saved", name=p.name),
            kb([[Btn(ctx.t("prod.add_another"), callback_data="prod:add"), Btn(ctx.t("home.products", n=repo.count(ctx.db, ctx.owner_shop.id)), callback_data="prod:list:0")], nav_row(ctx.lang)]),
        )
    else:
        await ctx.answer()


# --- edit one field --------------------------------------------------------------

EDIT_PROMPTS = {
    "name": "prod.name",
    "price": "prod.price",
    "stock": "prod.stock",
    "photo": "prod.send_new_photo",
    "description": "prod.desc_prompt",
}


async def begin_edit(ctx: Ctx, p: Product, fld: Optional[str]) -> None:
    if fld == "category":
        cats = repo.list_categories(ctx.db, ctx.owner_shop.id)
        rows = [[Btn(c.name, callback_data=f"prod:cat:{p.id}:{c.id}")] for c in cats[:20]]
        rows.append([Btn(ctx.t("prod.category_new"), callback_data=f"prod:cat:{p.id}:new"), Btn(ctx.t("prod.category_none"), callback_data=f"prod:cat:{p.id}:0")])
        rows.append(nav_row(ctx.lang, back=f"prod:view:{p.id}:0"))
        await ctx.render(ctx.t("prod.category"), kb(rows))
        return
    if fld not in EDIT_PROMPTS:
        return
    ctx.set_state(S.PROD_EDIT_FIELD, {"product_id": p.id, "field": fld})
    markup = skip_cancel(ctx.lang) if fld == "description" else cancel_only(ctx.lang)
    if fld == "stock":
        markup = kb([[Btn(ctx.t("prod.stock_unlimited"), callback_data="prodw:edit_unlimited")], [Btn(ctx.t("btn.cancel"), callback_data="cancel")]])
    await ctx.render(ctx.t(EDIT_PROMPTS[fld]), markup)


@on_state(S.PROD_EDIT_FIELD)
async def prod_edit_input(ctx: Ctx) -> None:
    d = ctx.data
    pid, fld = int(d.get("product_id", 0)), d.get("field")
    p = repo.get(ctx.db, ctx.owner_shop.id, pid) if ctx.owner_shop else None
    if p is None:
        ctx.reset()
        await ctx.send(ctx.t("prod.not_found"))
        return
    if fld == "name":
        if not 2 <= len(ctx.text) <= 80:
            await ctx.send(ctx.t("prod.name_invalid"))
            return
        p.name = ctx.text
    elif fld == "price":
        price = parse_price(ctx.text)
        if price is None:
            await ctx.send(ctx.t("prod.price_invalid"))
            return
        p.price_santim = price
    elif fld == "stock":
        if not ctx.text.isdigit():
            await ctx.send(ctx.t("prod.stock_invalid"))
            return
        p.stock = int(ctx.text)
    elif fld == "photo":
        if not ctx.msg.photo:
            await ctx.send(ctx.t("prod.need_photo"))
            return
        p.photo_file_id = ctx.msg.photo[-1].file_id
        p.photo_unique_id = ctx.msg.photo[-1].file_unique_id
    elif fld == "description":
        p.description = ctx.text[:500] or None
    elif fld == "category_new":
        if not 2 <= len(ctx.text) <= 48:
            await ctx.send(ctx.t("prod.category_invalid"))
            return
        p.category_id = repo.get_or_create_category(ctx.db, ctx.owner_shop.id, ctx.text).id
    ctx.db.flush()
    ctx.reset()
    await ctx.send(ctx.t("prod.updated"))
    if p.photo_file_id:
        await ctx.send_photo(p.photo_file_id, product_caption(ctx, p), product_card_kb(ctx, p, 0))
    else:
        await ctx.send(product_caption(ctx, p), product_card_kb(ctx, p, 0))


async def edit_unlimited(ctx: Ctx) -> None:
    d = ctx.data
    p = repo.update(ctx.db, ctx.owner_shop.id, int(d.get("product_id", 0)), stock=None)
    ctx.reset()
    if p:
        await ctx.answer(ctx.t("prod.updated"))
        await show_card(ctx, p, 0)
