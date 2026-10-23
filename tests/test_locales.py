"""Localization guardrails: both files stay in sync and nothing silently falls back to English."""
import re

from app.locales import LANGS, load, t
from app.services.money import fmt_price

ETHIOPIC = re.compile(r"[ሀ-፿]")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# Keys whose value is only symbols/placeholders or intentionally bilingual/command text.
ALLOWED_LATIN = {"lang.en", "lang.am", "adm.help"}


def test_same_keys_and_placeholders():
    en, am = load("en"), load("am")
    assert set(en) == set(am), set(en) ^ set(am)
    for k in en:
        assert set(PLACEHOLDER.findall(en[k])) == set(PLACEHOLDER.findall(am[k])), k


def test_amharic_is_translated():
    am = load("am")
    untranslated = [
        k for k, v in am.items()
        if k not in ALLOWED_LATIN and not ETHIOPIC.search(v) and LATIN_WORD.search(PLACEHOLDER.sub("", v))
    ]
    assert untranslated == [], untranslated


def test_prices_and_fallback():
    assert fmt_price(120000, "am") == "1,200 ብር" and fmt_price(120000, "en") == "ETB 1,200"
    assert t("btn.back", "am") != t("btn.back", "en")
    assert t("btn.back", "xx") == t("btn.back", "en")  # unknown lang file -> English text, never a crash
    assert t("no.such.key", "am") == "no.such.key"
    for lang in LANGS:
        assert len(load(lang)) > 250
