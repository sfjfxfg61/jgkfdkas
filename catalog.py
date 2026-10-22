"""Three region-sensitive one-time Stars products; signed invoices preserve their price."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
import time
from functools import lru_cache
from config import cfg

PERPETUAL = datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc)
MARKETS = ("ua", "cis", "latam", "asia", "eu", "us", "global")
# Prices aligned with common 100/250/500/1000-Star purchase tiers shown by Telegram.
# Exact top-up offers vary by account, region and platform and cannot be forced by bots.
DEFAULT_MATRIX = {
    "ua": {"trial": 100, "forever": 250, "vip": 500},
    "cis": {"trial": 100, "forever": 250, "vip": 500},
    "latam": {"trial": 100, "forever": 250, "vip": 500},
    "asia": {"trial": 100, "forever": 250, "vip": 500},
    "eu": {"trial": 250, "forever": 500, "vip": 1000},
    "us": {"trial": 250, "forever": 500, "vip": 1000},
    "global": {"trial": 250, "forever": 500, "vip": 1000},
}


@dataclass(frozen=True)
class Plan:
    code: str
    stars: int
    days: int


@dataclass(frozen=True)
class InvoiceDetails:
    code: str
    market: str
    amount: int
    days: int = 30


def default_market(lang: str) -> str:
    return {
        "uk": "ua",
        "ru": "cis",
        "es": "latam",
        "de": "eu",
        "fr": "eu",
        "it": "eu",
        "pt": "latam",
    }.get(lang, "global")


def clean_market(value: str | None) -> str:
    return value if value in MARKETS else "global"


@lru_cache(maxsize=1)
def matrix() -> dict[str, dict[str, int]]:
    result = {key: dict(prices) for key, prices in DEFAULT_MATRIX.items()}
    if cfg.price_matrix_json:
        result.update(json.loads(cfg.price_matrix_json))
    return result


NEW_CODES = ("secret", "mistress", "daddy")
LEGACY_CODES = ("trial", "forever", "vip")


def plans(market: str = "global") -> dict[str, Plan]:
    prices = matrix()[clean_market(market)]
    return {
        "secret": Plan("secret", prices["trial"], 30),
        "mistress": Plan("mistress", prices["forever"], cfg.personal_days),
        "daddy": Plan("daddy", prices["vip"], cfg.vip_days),
    }


def legacy_days(code: str) -> int:
    return {"trial": 7, "forever": 36500, "vip": cfg.vip_days}[code]


def promo_price(market: str) -> int:
    return max(1, plans(market)["daddy"].stars // 2)


def signature(data: str) -> str:
    return hmac.new(
        cfg.signing_key.encode(), data.encode(), hashlib.sha256
    ).hexdigest()[:24]


def new_payload(
    user_id: int,
    code: str,
    market: str = "global",
    now: int | None = None,
    *,
    promo_until: int | None = None,
    custom_amount: int | None = None,
) -> str:
    safe_market = clean_market(market)
    plan = plans(safe_market)[code]
    issue = int(now if now is not None else time.time())
    deadline = issue + 86400
    amount = plan.stars if custom_amount is None else custom_amount
    if type(amount) is not int or not 1 <= amount <= 10000:
        raise ValueError("Stars must be 1..10000")
    if (
        code == "daddy"
        and promo_until is not None
        and issue < promo_until <= issue + 7200
    ):
        amount, deadline = promo_price(safe_market), promo_until
    base = f"v4:{user_id}:{code}:{safe_market}:{amount}:{plan.days}:{issue}:{deadline}:{secrets.token_hex(4)}"
    payload = f"{base}:{signature(base)}"
    if len(payload.encode()) > 128:
        raise ValueError("Invoice payload exceeds Telegram limit")
    return payload


def parse_invoice(
    payload: str, user_id: int, amount: int, *, allow_expired: bool = False
) -> InvoiceDetails | None:
    fields = payload.split(":")
    if len(fields) == 10 and fields[0] == "v4":
        if not hmac.compare_digest(signature(":".join(fields[:9])), fields[9]):
            return None
        try:
            uid, price, days, issued, deadline = map(
                int, (fields[1], fields[4], fields[5], fields[6], fields[7])
            )
        except ValueError:
            return None
        if (
            uid != user_id
            or price != amount
            or not 1 <= price <= 10000
            or fields[2] not in NEW_CODES
            or fields[3] not in MARKETS
            or not 1 <= days <= 366
            or not issued < deadline <= issued + 86400
        ):
            return None
        if not allow_expired and (
            int(time.time()) >= deadline or issued > int(time.time()) + 120
        ):
            return None
        return InvoiceDetails(fields[2], fields[3], price, days)
    if len(fields) == 9 and fields[0] == "simple3":
        signed = ":".join(fields[:8])
        if not hmac.compare_digest(signature(signed), fields[8]):
            return None
        try:
            uid, price, issued, deadline = (
                int(fields[1]),
                int(fields[4]),
                int(fields[5]),
                int(fields[6]),
            )
        except ValueError:
            return None
        if (
            uid != user_id
            or fields[2] != "vip"
            or fields[3] not in ("eu", "us", "global")
            or price != 500
            or amount != 500
            or not (issued < deadline <= issued + 7200)
        ):
            return None
        if not allow_expired and (
            int(time.time()) >= deadline or issued > int(time.time()) + 120
        ):
            return None
        return InvoiceDetails("vip", fields[3], 500, cfg.vip_days)
    if len(fields) == 8 and fields[0] == "simple2":
        signed = ":".join(fields[:7])
        if not hmac.compare_digest(signature(signed), fields[7]):
            return None
        try:
            uid, price, issued = int(fields[1]), int(fields[4]), int(fields[5])
        except ValueError:
            return None
        code, market = fields[2], fields[3]
        if (
            uid != user_id
            or price != amount
            or price <= 0
            or code not in LEGACY_CODES
            or market not in MARKETS
        ):
            return None
        if not allow_expired and (
            int(time.time()) - issued > 24 * 3600 or issued > int(time.time()) + 120
        ):
            return None
        # Amount is signed, so price changes don't break invoices already issued.
        return InvoiceDetails(code, market, amount, legacy_days(code))
    # Compatibility with simple1 invoices already issued by the prior ZIP.
    if len(fields) == 7 and fields[0] == "simple1":
        signed = ":".join(fields[:6])
        if not hmac.compare_digest(signature(signed), fields[6]):
            return None
        try:
            uid, price, issued = int(fields[1]), int(fields[3]), int(fields[4])
        except ValueError:
            return None
        if (
            uid != user_id
            or price != amount
            or price <= 0
            or fields[2] not in LEGACY_CODES
        ):
            return None
        if not allow_expired and (
            int(time.time()) - issued > 24 * 3600 or issued > int(time.time()) + 120
        ):
            return None
        return InvoiceDetails(fields[2], "global", amount, legacy_days(fields[2]))
    return None


def parse_payload(
    payload: str, user_id: int, amount: int, *, allow_expired: bool = False
) -> str | None:
    invoice = parse_invoice(payload, user_id, amount, allow_expired=allow_expired)
    return invoice.code if invoice else None


def entitlement(
    user: dict | None, code: str, *, now: datetime | None = None
) -> datetime:
    now = now or datetime.now(timezone.utc)
    if code == "forever":
        return PERPETUAL
    old = (user or {}).get("premium_until")
    try:
        prior = datetime.fromisoformat(str(old).replace("Z", "+00:00")) if old else None
    except ValueError:
        prior = None
    base = max(now, prior) if prior and prior.year < 2099 else now
    return base + timedelta(
        days=(legacy_days(code) if code in LEGACY_CODES else plans()[code].days)
    )


def active(user: dict | None, now: datetime | None = None) -> bool:
    if not user or not (user.get("is_paid") or user.get("is_premium")):
        return False
    until = user.get("premium_until")
    if not until:
        return True  # preserve historical paid access
    try:
        date = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
        return date > (now or datetime.now(timezone.utc))
    except ValueError:
        return False
