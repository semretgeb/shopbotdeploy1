"""Customer side in chat: browse with buttons, cart, checkout wizard, my orders, payment screenshots."""
import re
from typing import Optional

from app.bot import states as S
from app.bot.context import Ctx
from app.bot.keyboards import Btn, cancel_only, kb, nav_row, paginator
from app.bot.router import arg, on_callback, on_state
from app.db.repo import customers as customers_repo
from app.db.repo import orders as orders_repo
from app.db.repo import products as products_repo
from app.db.repo import shops as shops_repo
from app.services import notifications as notif
from app.services import subscription as sub
from app.services.money import fmt_price

PAGE = 5
PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-]{7,15}$")


def _shop(ctx: Ctx):
    shop = shops_repo.get(ctx.db, ctx.state.shop_id) if ctx.state.shop_id else None
    return shop if shop and sub.is_shop_open(shop) else None


def _cart(ctx: Ctx) -> dict[str, int]:
    return {str(k): int(v) for k, v in (ctx.data.get("cart") or {}).items()}


def _cart_count(ctx: Ctx) -> int:
    return sum(_cart(ctx).values())


def _back_home(ctx: Ctx, back: Optional[str] = None):
    return nav_row(ctx.lang, back=back)


# --- browse ----------------------------------------------------------------------

async def show_categories(ctx: Ctx, shop) -> None:
    cats = products_repo.list_categories(ctx.db, shop.id)
    counts = products_repo.category_counts(ctx.db, shop.id)
    total = sum(counts.values())
    rows = [[Btn(ctx.t("cust.browse_all", n=total), callback_data="cust:products:0:0")]]
    for c in cats:
        if counts.get(c.id):
            rows.append([Btn(f"{c.name} ({counts[c.id]})", callback_data=f"cust:products:{c.id}:0")])
    rows.append([Btn(ctx.t("cust.cart", n=_cart_count(ctx)), callback_data="cust:cart")])
    rows.append(_back_home(ctx))
    await ctx.render(ctx.t("cust.browse_title", shop=shop.name), kb(rows))


async def show_products(ctx: Ctx, shop, category_id: int, page: int) -> None:
    items, total = products_repo.list_page(ctx.db, shop.id, page, PAGE, category_id or None, active_only=True)
    cat = products_repo.get_category(ctx.db, shop.id, category_id) if category_id else None
    title = ctx.t("cust.products_title", category=cat.name if cat else ctx.t("app.all"), n=total)
    if not items:
        await ctx.render(title + "\n\n" + ctx.t("cust.products_empty"), kb([_back_home(ctx, back="cust:browse")]))
        return
    rows = [[Btn(ctx.t("cust.product_row", name=p.name, price=fmt_price(p.price_santim, ctx.lang))[:60], callback_data=f"cust:view:{p.id}:{category_id}:{page}")] for p in items]
    rows.append(paginator(ctx.lang, "custp", page, total, PAGE, str(category_id)))
    rows.append([Btn(ctx.t("cust.cart", n=_cart_count(ctx)), callback_data="cust:cart")])
    rows.append(_back_home(ctx, back="cust:browse"))
    await ctx.render(title, kb(rows))


async def show_product(ctx: Ctx, shop, p, category_id: int, page: int) -> None:
    if p.stock is None:
        stock = ""
    elif p.stock <= 0:
        stock = ctx.t("prod.stock_label_out")
    else:
        stock = ctx.t("prod.stock_label_n", n=p.stock)
    text = ctx.t("cust.product_card", name=p.name, price=fmt_price(p.price_santim, ctx.lang), stock=stock, desc=p.description or "").strip()
    rows = []
    if p.stock is None or p.stock > 0:
        rows.append([Btn(ctx.t("cust.add"), callback_data=f"cust:add:{p.id}:{category_id}:{page}")])
    rows.append([Btn(ctx.t("cust.cart", n=_cart_count(ctx)), callback_data="cust:cart")])
    rows.append(_back_home(ctx, back=f"cust:products:{category_id}:{page}"))
    markup = kb(rows)
    if p.photo_file_id:
        await ctx.edit_photo_card(p.photo_file_id, text, markup)
    else:
        await ctx.render(text, markup)


# --- cart ----------------------------------------------------------------------------

def _cart_lines(ctx: Ctx, shop) -> tuple[str, int, list]:
    lines, total, valid = [], 0, []
    for pid, qty in _cart(ctx).items():
        p = products_repo.get(ctx.db, shop.id, int(pid))
        if p is None or not p.is_active or (p.stock is not None and p.stock <= 0):
            continue
        if p.stock is not None:
            qty = min(qty, p.stock)
        line = p.price_santim * qty
        total += line
        lines.append(ctx.t("cust.cart_line", name=p.name, qty=qty, total=fmt_price(line, ctx.lang)))
        valid.append((p, qty))
    return "\n".join(lines), total, valid


async def show_cart(ctx: Ctx, shop) -> None:
    items_text, total, valid = _cart_lines(ctx, shop)
    if not valid:
        ctx.update_data(cart={})
        await ctx.render(ctx.t("cust.cart_empty"), kb([[Btn(ctx.t("cust.continue"), callback_data="cust:browse")], _back_home(ctx)]))
        return
    ctx.update_data(cart={str(p.id): q for p, q in valid})
    rows = [[Btn(ctx.t("cust.remove", name=p.name)[:60], callback_data=f"cust:rm:{p.id}")] for p, _ in valid]
    rows.append([Btn(ctx.t("cust.checkout"), callback_data="cust:checkout"), Btn(ctx.t("cust.continue"), callback_data="cust:browse")])
    rows.append([Btn(ctx.t("cust.clear"), callback_data="cust:clear")])
    rows.append(_back_home(ctx))
    await ctx.render(ctx.t("cust.cart_title", items=items_text, total=fmt_price(total, ctx.lang)), kb(rows))


# --- checkout wizard -------------------------------------------------------------------

async def ask_name(ctx: Ctx, shop) -> None:
    cust = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    ctx.set_state(S.CUST_NAME, ctx.data)
    rows = []
    if cust.full_name:
        rows.append([Btn(ctx.t("cust.use_saved", value=cust.full_name)[:60], callback_data="custw:name")])
    rows.append([Btn(ctx.t("btn.cancel"), callback_data="cancel")])
    await ctx.send(ctx.t("cust.ask_name"), kb(rows))


async def ask_phone(ctx: Ctx, shop) -> None:
    cust = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    ctx.set_state(S.CUST_PHONE, ctx.data)
    rows = []
    if cust.phone:
        rows.append([Btn(ctx.t("cust.use_saved", value=cust.phone), callback_data="custw:phone")])
    rows.append([Btn(ctx.t("btn.cancel"), callback_data="cancel")])
    await ctx.send(ctx.t("cust.ask_phone"), kb(rows))


async def ask_address(ctx: Ctx, shop) -> None:
    cust = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    ctx.set_state(S.CUST_ADDRESS, ctx.data)
    rows = []
    if cust.address:
        rows.append([Btn(ctx.t("cust.use_saved", value=cust.address)[:60], callback_data="custw:address")])
    rows.append([Btn(ctx.t("btn.cancel"), callback_data="cancel")])
    await ctx.send(ctx.t("cust.ask_address"), kb(rows))


async def ask_payment(ctx: Ctx, shop) -> None:
    ctx.set_state(S.CUST_PAYMENT, ctx.data)
    rows = [[Btn(ctx.t("cust.pay_cod"), callback_data="custw:pay:cod")]]
    if shop.payment_info:
        rows.append([Btn(ctx.t("cust.pay_transfer"), callback_data="custw:pay:transfer")])
    rows.append([Btn(ctx.t("btn.cancel"), callback_data="cancel")])
    await ctx.send(ctx.t("cust.ask_payment"), kb(rows))


async def show_confirm(ctx: Ctx, shop) -> None:
    d = ctx.data
    items_text, total, valid = _cart_lines(ctx, shop)
    if not valid:
        await show_cart(ctx, shop)
        return
    ctx.set_state(S.CUST_CONFIRM, d)
    pay = ctx.t("cust.pay_cod" if d.get("payment") == "cod" else "cust.pay_transfer")
    text = ctx.t("cust.confirm_title", items=items_text, total=fmt_price(total, ctx.lang), name=d.get("name", ""), phone=d.get("phone", ""), address=d.get("address", ""), pay=pay)
    await ctx.send(text, kb([[Btn(ctx.t("cust.place"), callback_data="custw:place")], [Btn(ctx.t("btn.cancel"), callback_data="cancel")]]))


async def place_order(ctx: Ctx, shop) -> None:
    d = ctx.data
    _, _, valid = _cart_lines(ctx, shop)
    customer = customers_repo.save_details(ctx.db, shop.id, ctx.user.id, d.get("name"), d.get("phone"), d.get("address"))
    try:
        order = orders_repo.create(
            ctx.db, shop.id, customer.id, [(p.id, q) for p, q in valid],
            full_name=d.get("name", ""), phone=d.get("phone", ""), address=d.get("address", ""),
            payment_method=d.get("payment", "cod"), source="chat",
        )
    except orders_repo.OrderError as e:
        ctx.set_state(S.IDLE, {"cart": _cart(ctx)})
        await ctx.send(ctx.t("cust.order_failed", reason=ctx.t(f"order.err_{e.code}")))
        await show_cart(ctx, shop)
        return
    ctx.db.commit()
    await notif.notify_new_order(ctx.tg.bot, ctx.db, shop, order, customer)
    ctx.db.commit()
    if order.payment_method == "transfer":
        ctx.set_state(S.CUST_PROOF, {"order_id": order.id})
    else:
        ctx.set_state(S.IDLE, {})
    await ctx.send(ctx.t("cust.placed", code=order.code), kb([[Btn(ctx.t("cust.continue"), callback_data="cust:browse")], _back_home(ctx)]))


@on_state(S.CUST_NAME)
async def cust_name(ctx: Ctx) -> None:
    shop = _shop(ctx)
    if not shop:
        ctx.reset()
        return
    if not 2 <= len(ctx.text) <= 80:
        await ctx.send(ctx.t("cust.invalid_name"))
        return
    ctx.update_data(name=ctx.text)
    await ask_phone(ctx, shop)


@on_state(S.CUST_PHONE)
async def cust_phone(ctx: Ctx) -> None:
    shop = _shop(ctx)
    if not shop:
        ctx.reset()
        return
    phone = ctx.msg.contact.phone_number if ctx.msg.contact else ctx.text
    if not phone or not PHONE_RE.match(phone):
        await ctx.send(ctx.t("cust.invalid_phone"))
        return
    ctx.update_data(phone=phone)
    await ask_address(ctx, shop)


@on_state(S.CUST_ADDRESS)
async def cust_address(ctx: Ctx) -> None:
    shop = _shop(ctx)
    if not shop:
        ctx.reset()
        return
    if len(ctx.text) < 3:
        await ctx.send(ctx.t("cust.invalid_address"))
        return
    ctx.update_data(address=ctx.text[:500])
    await ask_payment(ctx, shop)


@on_state(S.CUST_PAYMENT, S.CUST_CONFIRM)
async def cust_wait_for_button(ctx: Ctx) -> None:
    shop = _shop(ctx)
    if shop:
        await (ask_payment if ctx.state.state == S.CUST_PAYMENT else show_confirm)(ctx, shop)


@on_state(S.CUST_PROOF)
async def cust_proof(ctx: Ctx) -> None:
    shop = _shop(ctx)
    if not shop:
        ctx.reset()
        return
    if not ctx.msg.photo:
        await ctx.send(ctx.t("cust.send_proof"), kb([_back_home(ctx)]))
        return
    await attach_proof(ctx, shop, int(ctx.data.get("order_id", 0)), ctx.msg.photo[-1].file_id)


async def attach_proof(ctx: Ctx, shop, order_id: int, file_id: str) -> bool:
    customer = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    order = orders_repo.get_for_customer(ctx.db, shop.id, customer.id, order_id)
    if order is None:
        return False
    orders_repo.set_proof(ctx.db, shop.id, order.id, file_id)
    ctx.db.commit()
    # The photo already lives in Telegram; forward it to the owner as a reply to the order card.
    try:
        await ctx.tg.bot.send_photo(shop.owner_id, file_id, caption=ctx.t("order.new_proof", code=order.code),
                                    reply_to_message_id=order.owner_msg_id, allow_sending_without_reply=True)
    except Exception:
        pass
    await notif.refresh_owner_card(ctx.tg.bot, shop, order)
    ctx.set_state(S.IDLE, {})
    await ctx.send(ctx.t("cust.proof_received"), kb([_back_home(ctx)]))
    return True


async def photo_while_idle(ctx: Ctx, shop) -> bool:
    """Customer sent a photo with no active state: attach to their newest unpaid transfer order."""
    customer = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    pending = [o for o in orders_repo.list_for_customer(ctx.db, shop.id, customer.id, 10)
               if o.payment_method == "transfer" and o.status in ("pending", "confirmed") and not o.payment_proof_file_id]
    if not pending:
        return False
    if len(pending) == 1:
        return await attach_proof(ctx, shop, pending[0].id, ctx.msg.photo[-1].file_id)
    ctx.update_data(pending_proof=ctx.msg.photo[-1].file_id)
    rows = [[Btn(f"#{o.code} · {fmt_price(o.total_santim, ctx.lang)}", callback_data=f"custw:proof:{o.id}")] for o in pending[:5]]
    await ctx.send(ctx.t("cust.proof_which"), kb(rows + [[Btn(ctx.t("btn.cancel"), callback_data="cancel")]]))
    return True


# --- my orders ------------------------------------------------------------------------------

async def show_my_orders(ctx: Ctx, shop) -> None:
    customer = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    orders = orders_repo.list_for_customer(ctx.db, shop.id, customer.id, 10)
    if not orders:
        await ctx.render(ctx.t("cust.orders_empty"), kb([[Btn(ctx.t("cust.continue"), callback_data="cust:browse")], _back_home(ctx)]))
        return
    rows = [[Btn(ctx.t("cust.order_row", code=o.code, total=fmt_price(o.total_santim, ctx.lang), status=ctx.t(notif.STATUS_KEYS[o.status]))[:60], callback_data=f"cust:order:{o.id}")] for o in orders]
    rows.append(_back_home(ctx))
    await ctx.render(ctx.t("cust.orders_title"), kb(rows))


# --- callbacks ----------------------------------------------------------------------------------

@on_callback("custp")
async def cust_page_cb(ctx: Ctx) -> None:
    await ctx.answer()
    shop = _shop(ctx)
    if shop:
        await show_products(ctx, shop, int(arg(ctx, 3, "0")), int(arg(ctx, 2, "0")))


@on_callback("cust")
async def cust_cb(ctx: Ctx) -> None:
    from app.bot.handlers.start import customer_home, show_entry

    shop = _shop(ctx)
    if shop is None:
        await ctx.answer()
        await show_entry(ctx)
        return
    action = arg(ctx, 1)
    if action == "contact":
        await ctx.answer()
        await ctx.render(ctx.t("customer.contact_text", shop=shop.name, phone=shop.phone or ctx.t("not_set")), kb([_back_home(ctx)]))
    elif action == "browse":
        await ctx.answer()
        await show_categories(ctx, shop)
    elif action == "products":
        await ctx.answer()
        await show_products(ctx, shop, int(arg(ctx, 2, "0")), int(arg(ctx, 3, "0")))
    elif action == "view":
        await ctx.answer()
        p = products_repo.get(ctx.db, shop.id, int(arg(ctx, 2, "0")))
        if p and p.is_active:
            await show_product(ctx, shop, p, int(arg(ctx, 3, "0")), int(arg(ctx, 4, "0")))
        else:
            await ctx.answer(ctx.t("prod.not_found"), alert=True)
    elif action == "add":
        p = products_repo.get(ctx.db, shop.id, int(arg(ctx, 2, "0")))
        if p is None or not p.is_active:
            await ctx.answer(ctx.t("prod.not_found"), alert=True)
            return
        cart = _cart(ctx)
        cart[str(p.id)] = min(99, cart.get(str(p.id), 0) + 1)
        ctx.update_data(cart=cart)
        await ctx.answer(ctx.t("cust.added", name=p.name))
        await show_product(ctx, shop, p, int(arg(ctx, 3, "0")), int(arg(ctx, 4, "0")))
    elif action == "cart":
        await ctx.answer()
        await show_cart(ctx, shop)
    elif action == "rm":
        cart = _cart(ctx)
        cart.pop(arg(ctx, 2, ""), None)
        ctx.update_data(cart=cart)
        await ctx.answer()
        await show_cart(ctx, shop)
    elif action == "clear":
        ctx.update_data(cart={})
        await ctx.answer()
        await show_cart(ctx, shop)
    elif action == "checkout":
        await ctx.answer()
        if not _cart(ctx):
            await show_cart(ctx, shop)
            return
        await ask_name(ctx, shop)
    elif action == "orders":
        await ctx.answer()
        await show_my_orders(ctx, shop)
    elif action == "order":
        await ctx.answer()
        customer = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
        o = orders_repo.get_for_customer(ctx.db, shop.id, customer.id, int(arg(ctx, 2, "0")))
        if o:
            await ctx.render(notif.customer_status_text(o, shop, ctx.lang), kb([_back_home(ctx, back="cust:orders")]))
    elif action == "ask":
        await ctx.answer()
        ctx.set_state(S.CUST_ASK, ctx.data)
        await ctx.render(ctx.t("ai.ask_prompt", shop=shop.name), kb([_back_home(ctx)]))
    else:
        await ctx.answer()
        await customer_home(ctx, shop)


@on_callback("custw")
async def cust_wizard_cb(ctx: Ctx) -> None:
    """Buttons inside the chat checkout."""
    shop = _shop(ctx)
    if shop is None:
        await ctx.answer()
        return
    action = arg(ctx, 1)
    st = ctx.state.state
    cust = customers_repo.get_or_create(ctx.db, shop.id, ctx.user.id)
    await ctx.answer()
    if action == "name" and st == S.CUST_NAME and cust.full_name:
        ctx.update_data(name=cust.full_name)
        await ask_phone(ctx, shop)
    elif action == "phone" and st == S.CUST_PHONE and cust.phone:
        ctx.update_data(phone=cust.phone)
        await ask_address(ctx, shop)
    elif action == "address" and st == S.CUST_ADDRESS and cust.address:
        ctx.update_data(address=cust.address)
        await ask_payment(ctx, shop)
    elif action == "pay" and st == S.CUST_PAYMENT:
        ctx.update_data(payment="transfer" if arg(ctx, 2) == "transfer" and shop.payment_info else "cod")
        await show_confirm(ctx, shop)
    elif action == "place" and st == S.CUST_CONFIRM:
        await place_order(ctx, shop)
    elif action == "proof":
        file_id = ctx.data.get("pending_proof")
        if file_id:
            await attach_proof(ctx, shop, int(arg(ctx, 2, "0")), file_id)
