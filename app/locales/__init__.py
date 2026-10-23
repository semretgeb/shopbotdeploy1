"""Tiny i18n layer shared by the bot and (via /api/i18n) the Mini App.

Translation files are flat JSON: {"key": "text with {placeholders}"}.
Missing keys fall back to English, then to the key itself (never crash on a missing string).
"""
import json
from functools import lru_cache
from pathlib import Path

LANGS = ("am", "en")
DEFAULT_LANG = "am"
_DIR = Path(__file__).parent


@lru_cache
def load(lang: str) -> dict[str, str]:
    path = _DIR / f"{lang}.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def t(key: str, lang: str = DEFAULT_LANG, **kw) -> str:
    text = load(lang).get(key) or load("en").get(key) or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text


def norm_lang(lang: str | None) -> str:
    return lang if lang in LANGS else DEFAULT_LANG
