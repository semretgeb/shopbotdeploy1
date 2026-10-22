"""Verification of Telegram Mini App initData.

Spec: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
  secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
  hash       = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
  data_check_string = "\n".join(sorted(f"{k}={v}" for k, v not in {"hash"}))
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import parse_qsl


class InitDataError(Exception):
    pass


@dataclass
class InitData:
    user: dict[str, Any]
    auth_date: int
    start_param: Optional[str] = None
    raw: dict[str, str] = field(default_factory=dict)

    @property
    def user_id(self) -> int:
        return int(self.user["id"])


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def compute_hash(fields: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()) if k != "hash")
    return hmac.new(_secret_key(bot_token), data_check_string.encode(), hashlib.sha256).hexdigest()


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> InitData:
    """Raises InitDataError on any problem. Never trust fields before this returns."""
    if not init_data:
        raise InitDataError("missing")
    try:
        fields = dict(parse_qsl(init_data, strict_parsing=True, keep_blank_values=True))
    except ValueError as e:
        raise InitDataError("malformed") from e

    received = fields.get("hash")
    if not received:
        raise InitDataError("no_hash")
    if not hmac.compare_digest(compute_hash(fields, bot_token), received):
        raise InitDataError("bad_signature")

    try:
        auth_date = int(fields.get("auth_date", "0"))
    except ValueError as e:
        raise InitDataError("bad_auth_date") from e
    if max_age_seconds and time.time() - auth_date > max_age_seconds:
        raise InitDataError("expired")

    try:
        user = json.loads(fields.get("user", ""))
        int(user["id"])
    except (ValueError, KeyError, TypeError) as e:
        raise InitDataError("no_user") from e

    return InitData(user=user, auth_date=auth_date, start_param=fields.get("start_param"), raw=fields)


def build_init_data(fields: dict[str, Any], bot_token: str) -> str:
    """Test helper: builds a correctly signed initData string (used by tests and local dev)."""
    from urllib.parse import urlencode

    flat = {k: (json.dumps(v, separators=(",", ":")) if isinstance(v, (dict, list)) else str(v)) for k, v in fields.items()}
    flat["hash"] = compute_hash(flat, bot_token)
    return urlencode(flat)
