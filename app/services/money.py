"""Prices are stored as integer santim (1 birr = 100 santim) to avoid float errors."""
import re
from typing import Optional

_NUM_RE = re.compile(r"^\s*(?:etb|birr|ብር)?\s*([0-9][0-9,]*)(?:\.([0-9]{1,2}))?\s*(?:etb|birr|ብር)?\s*$", re.I)


def fmt_price(santim: int, lang: str = "am") -> str:
    birr, rest = divmod(abs(int(santim)), 100)
    num = f"{birr:,}" if rest == 0 else f"{birr:,}.{rest:02d}"
    if santim < 0:
        num = "-" + num
    return f"{num} ብር" if lang == "am" else f"ETB {num}"


def parse_price(text: str) -> Optional[int]:
    """'1,200' / '1200.50' / 'ETB 1200' / '1200 ብር' -> santim. None if invalid or non-positive."""
    m = _NUM_RE.match(text or "")
    if not m:
        return None
    birr = int(m.group(1).replace(",", ""))
    cents = int((m.group(2) or "0").ljust(2, "0"))
    total = birr * 100 + cents
    return total if total > 0 else None
