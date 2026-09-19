from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from config import settings


SUBSCRIPTION_PERIOD = 2_592_000
MARKETS = {"ua", "cis", "latam", "eu", "us", "global"}


@dataclass(frozen=True, slots=True)
class Entitlements:
    daily_messages: int
    history_messages: int
    memories: int
    model: str
    proactive: bool


@dataclass(frozen=True, slots=True)
class Product:
    code: str
    tier: str
    duration_days: int
    recurring: bool
    title: str
    badge: str


# Внутренние коды plus/pro/ultra/black менять нельзя.
PRODUCTS: dict[str, Product] = {
    "plus": Product(
        code="plus",
        tier="plus",
        duration_days=30,
        recurring=True,
        title="Plus",
        badge="",
    ),
    "pro": Product(
        code="pro",
        tier="pro",
        duration_days=30,
        recurring=True,
        title="Private Chat",
        badge="MOST POPULAR",
    ),
    "ultra": Product(
        code="ultra",
        tier="ultra",
        duration_days=30,
        recurring=True,
        title="Ultra",
        badge="BEST EXPERIENCE",
    ),
    "black": Product(
        code="black",
        tier="black",
        duration_days=365,
        recurring=False,
        title="Private + Calls",
        badge="HIGH VALUE",
    ),
}


PRODUCT_TITLES: dict[str, dict[str, str]] = {
    "ru": {
        "plus": "Plus",
        "pro": "Приватный чат",
        "ultra": "Ultra",
        "black": "Приватный чат + звонки",
    },
    "uk": {
        "plus": "Plus",
        "pro": "Приватний чат",
        "ultra": "Ultra",
        "black": "Приватний чат + дзвінки",
    },
    "en": {
        "plus": "Plus",
        "pro": "Private Chat",
        "ultra": "Ultra",
        "black": "Private + Calls",
    },
    "es": {
        "plus": "Plus",
        "pro": "Chat privado",
        "ultra": "Ultra",
        "black": "Chat privado + llamadas",
    },
    "de": {
        "plus": "Plus",
        "pro": "Privater Chat",
        "ultra": "Ultra",
        "black": "Privater Chat + Anrufe",
    },
    "fr": {
        "plus": "Plus",
        "pro": "Chat privé",
        "ultra": "Ultra",
        "black": "Chat privé + appels",
    },
}


ENTITLEMENTS: dict[str, Entitlements] = {
    "free": Entitlements(
        20,
        12,
        10,
        settings.ai_model,
        False,
    ),
    "plus": Entitlements(
        100,
        30,
        30,
        settings.ai_model,
        True,
    ),
    "pro": Entitlements(
        300,
        60,
        100,
        settings.pro_ai_model,
        True,
    ),
    "ultra": Entitlements(
        800,
        100,
        250,
        settings.ultra_ai_model,
        True,
    ),
    "black": Entitlements(
        800,
        100,
        250,
        settings.ultra_ai_model,
        True,
    ),
}


# Внутри каждой страны ключи менять нельзя.
PRICE_MATRIX: dict[str, dict[str, int]] = {
    "ua": {
        "plus": 249,
        "pro": 549,
        "ultra": 1_299,
        "black": 4_999,
    },
    "cis": {
        "plus": 299,
        "pro": 699,
        "ultra": 1_499,
        "black": 5_499,
    },
    "latam": {
        "plus": 349,
        "pro": 799,
        "ultra": 1_799,
        "black": 5_999,
    },
    "eu": {
        "plus": 599,
        "pro": 1_399,
        "ultra": 3_299,
        "black": 8_499,
    },
    "us": {
        "plus": 899,
        "pro": 2_199,
        "ultra": 4_999,
        "black": 9_999,
    },
    "global": {
        "plus": 499,
        "pro": 1_099,
        "ultra": 2_499,
        "black": 6_999,
    },
}


def product_title(lang: str, product_code: str) -> str:
    titles = PRODUCT_TITLES.get(lang, PRODUCT_TITLES["en"])
    return titles.get(product_code, PRODUCTS[product_code].title)


def default_market(lang: str, ref: str = "") -> str:
    del ref

    return {
        "uk": "ua",
        "ru": "cis",
        "es": "latam",
        "de": "eu",
        "fr": "eu",
        "en": "us",
    }.get(lang, "global")


def price(market: str, product_code: str) -> int:
    safe_market = market if market in PRICE_MATRIX else "global"

    if product_code not in PRODUCTS:
        raise ValueError(f"Unknown product: {product_code}")

    return PRICE_MATRIX[safe_market][product_code]


def entitlements(tier: str | None) -> Entitlements:
    return ENTITLEMENTS.get(
        tier or "free",
        ENTITLEMENTS["free"],
    )


def make_payload(
    user_id: int,
    product_code: str,
    market: str,
) -> str:
    if product_code not in PRODUCTS or market not in MARKETS:
        raise ValueError("Unknown product or market")

    body = f"v2:{user_id}:{product_code}:{market}"
    signing_secret = settings.payment_secret or settings.bot_token

    signature = hmac.new(
        signing_secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()[:20]

    return f"{body}:{signature}"


def parse_payload(
    payload: str,
    expected_user_id: int,
) -> tuple[Product, str] | None:
    try:
        version, raw_user_id, product_code, market, signature = payload.split(":")
        user_id = int(raw_user_id)
    except (ValueError, AttributeError):
        return None

    if (
        version != "v2"
        or user_id != expected_user_id
        or product_code not in PRODUCTS
        or market not in MARKETS
    ):
        return None

    body = f"{version}:{user_id}:{product_code}:{market}"
    signing_secret = settings.payment_secret or settings.bot_token

    expected = hmac.new(
        signing_secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()[:20]

    if not hmac.compare_digest(signature, expected):
        return None

    return PRODUCTS[product_code], market


def paywall_text(lang: str, market: str) -> str:
    prices = {
        code: price(market, code)
        for code in PRODUCTS
    }

    names = {
        code: product_title(lang, code)
        for code in PRODUCTS
    }

    if lang == "ru":
        return (
            "<b>Выберите подходящий тариф</b>\n\n"
            f"⚡ <b>{names['plus']} · {prices['plus']} ⭐/мес</b>\n"
            f"🔥 <b>{names['pro']} · {prices['pro']} ⭐/мес — выбор большинства</b>\n"
            f"🚀 <b>{names['ultra']} · {prices['ultra']} ⭐/мес</b>\n"
            f"💎 <b>{names['black']} · {prices['black']} ⭐/год</b>"
        )

    if lang == "uk":
        return (
            "<b>Оберіть відповідний тариф</b>\n\n"
            f"⚡ <b>{names['plus']} · {prices['plus']} ⭐/міс</b>\n"
            f"🔥 <b>{names['pro']} · {prices['pro']} ⭐/міс — вибір більшості</b>\n"
            f"🚀 <b>{names['ultra']} · {prices['ultra']} ⭐/міс</b>\n"
            f"💎 <b>{names['black']} · {prices['black']} ⭐/рік</b>"
        )

    if lang == "es":
        return (
            "<b>Elige tu plan</b>\n\n"
            f"⚡ <b>{names['plus']} · {prices['plus']} ⭐/mes</b>\n"
            f"🔥 <b>{names['pro']} · {prices['pro']} ⭐/mes — más popular</b>\n"
            f"🚀 <b>{names['ultra']} · {prices['ultra']} ⭐/mes</b>\n"
            f"💎 <b>{names['black']} · {prices['black']} ⭐/año</b>"
        )

    if lang == "de":
        return (
            "<b>Wähle deinen Tarif</b>\n\n"
            f"⚡ <b>{names['plus']} · {prices['plus']} ⭐/Monat</b>\n"
            f"🔥 <b>{names['pro']} · {prices['pro']} ⭐/Monat — beliebt</b>\n"
            f"🚀 <b>{names['ultra']} · {prices['ultra']} ⭐/Monat</b>\n"
            f"💎 <b>{names['black']} · {prices['black']} ⭐/Jahr</b>"
        )

    if lang == "fr":
        return (
            "<b>Choisis ton forfait</b>\n\n"
            f"⚡ <b>{names['plus']} · {prices['plus']} ⭐/mois</b>\n"
            f"🔥 <b>{names['pro']} · {prices['pro']} ⭐/mois — populaire</b>\n"
            f"🚀 <b>{names['ultra']} · {prices['ultra']} ⭐/mois</b>\n"
            f"💎 <b>{names['black']} · {prices['black']} ⭐/an</b>"
        )

    return (
        "<b>Choose Your Plan</b>\n\n"
        f"⚡ <b>{names['plus']} · {prices['plus']} ⭐/month</b>\n"
        f"🔥 <b>{names['pro']} · {prices['pro']} ⭐/month — most popular</b>\n"
        f"🚀 <b>{names['ultra']} · {prices['ultra']} ⭐/month</b>\n"
        f"💎 <b>{names['black']} · {prices['black']} ⭐/year</b>"
    )
