"""ASCII-only, never-editable shop slugs: 'Abebe Fashion & Co' -> 'abebe-fashion-co'.
Amharic-only names (no ASCII letters) get a random id like 'shop-k3x9m2'."""
import re
import secrets
import string
import unicodedata

_ALPHABET = string.ascii_lowercase + string.digits
_MAX_LEN = 40


def _random_id(n: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)[:_MAX_LEN].strip("-")
    return s


def make_slug(name: str, taken: set[str]) -> str:
    base = slugify(name)
    if len(base) < 3:
        base = "shop"
    candidate = base if base != "shop" else f"shop-{_random_id()}"
    while candidate in taken:
        candidate = f"{base[:_MAX_LEN - 7]}-{_random_id()}"
    return candidate
