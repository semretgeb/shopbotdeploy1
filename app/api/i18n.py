"""Serves the same translation files the bot uses, so the Mini App never hardcodes copy."""
import hashlib
import json

from fastapi import APIRouter, Request, Response

from app.locales import LANGS, load

router = APIRouter(prefix="/api")


@router.get("/i18n/{lang}", include_in_schema=False)
def get_translations(lang: str, request: Request) -> Response:
    lang = lang if lang in LANGS else "am"
    body = json.dumps(load(lang), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    etag = '"' + hashlib.md5(body).hexdigest()[:16] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(body, media_type="application/json; charset=utf-8", headers={"ETag": etag, "Cache-Control": "public, max-age=3600"})
