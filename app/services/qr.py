"""QR code PNG for a shop link (generated on demand, never stored)."""
import io

import qrcode
from qrcode.image.pil import PilImage


def shop_link(bot_username: str, slug: str) -> str:
    return f"https://t.me/{bot_username}?start={slug}"


def qr_png(data: str, box_size: int = 10) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
