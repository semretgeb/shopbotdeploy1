"""Shop link + QR code for sharing."""
from telegram import CopyTextButton
from telegram.constants import ParseMode

from app.bot.context import Ctx
from app.bot.keyboards import Btn, kb, nav_row
from app.bot.router import arg, on_callback
from app.config import get_settings
from app.services.qr import qr_png, shop_link


@on_callback("share")
async def share_cb(ctx: Ctx) -> None:
    await ctx.answer()
    shop = ctx.owner_shop
    if shop is None:
        return
    if arg(ctx, 1) == "forward":
        await send_customer_message(ctx)
        return
    link = shop_link(get_settings().BOT_USERNAME, shop.slug)
    q = ctx.update.callback_query
    if q and q.message and not q.message.photo:
        try:
            await q.message.delete()
        except Exception:
            pass
    await ctx.tg.bot.send_photo(
        ctx.chat_id,
        qr_png(link),
        caption=ctx.t("share.text", link=link),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb([
            [Btn(ctx.t("share.copy"), copy_text=CopyTextButton(link))],
            [Btn(ctx.t("share.forward"), callback_data="share:forward")],
            nav_row(ctx.lang),
        ]),
    )


async def send_customer_message(ctx: Ctx) -> None:
    """A clean message with only the link, meant to be forwarded to customers."""
    shop = ctx.owner_shop
    link = shop_link(get_settings().BOT_USERNAME, shop.slug)
    await ctx.send(ctx.t("share.customer_msg", shop=shop.name, link=link))

