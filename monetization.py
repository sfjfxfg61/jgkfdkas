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


PRODUCTS: dict[str, Product] = {
    "plus": Product("plus", "plus", 30, True, "Plus", ""),
    "pro": Product("pro", "pro", 30, True, "Pro", "MOST POPULAR"),
    "ultra": Product("ultra", "ultra", 30, True, "Ultra", "BEST EXPERIENCE"),
    "black": Product("black", "black", 365, False, "Black · 1 year", "HIGH VALUE"),
}

ENTITLEMENTS: dict[str, Entitlements] = {
    "free": Entitlements(20, 12, 10, settings.ai_model, False),
    "plus": Entitlements(100, 30, 30, settings.ai_model, True),
    "pro": Entitlements(300, 60, 100, settings.pro_ai_model, True),
    "ultra": Entitlements(800, 100, 250, settings.ultra_ai_model, True),
    "black": Entitlements(800, 100, 250, settings.ultra_ai_model, True),
}

# Prices are in Telegram Stars. Keep every recurring price <= 10,000 Stars.
PRICE_MATRIX: dict[str, dict[str, int]] = {
    "ua": {"plus": 249, "pro": 549, "ultra": 1_299, "black": 4_999},
    "cis": {"plus": 299, "pro": 699, "ultra": 1_499, "black": 5_499},
    "latam": {"plus": 349, "pro": 799, "ultra": 1_799, "black": 5_999},
    "eu": {"plus": 599, "pro": 1_399, "ultra": 3_299, "black": 8_499},
    "us": {"plus": 899, "pro": 2_199, "ultra": 4_999, "black": 9_999},
    "global": {"plus": 499, "pro": 1_099, "ultra": 2_499, "black": 6_999},
}

MARKET_NAMES = {
    "ua": "Ukraine",
    "cis": "Eastern Europe",
    "latam": "Latin America",
    "eu": "EU / UK",
    "us": "USA / Canada",
    "global": "Global",
}


def default_market(lang: str, ref: str = "") -> str:
    """Select prices only from Telegram's language code; campaign refs never override it."""
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
    return PRICE_MATRIX[safe_market][product_code]


def entitlements(tier: str | None) -> Entitlements:
    return ENTITLEMENTS.get(tier or "free", ENTITLEMENTS["free"])


def make_payload(user_id: int, product_code: str, market: str) -> str:
    if product_code not in PRODUCTS or market not in MARKETS:
        raise ValueError("Unknown product or market")
    body = f"v2:{user_id}:{product_code}:{market}"
    signing_secret = settings.payment_secret or settings.bot_token
    signature = hmac.new(signing_secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{body}:{signature}"


def parse_payload(payload: str, expected_user_id: int) -> tuple[Product, str] | None:
    try:
        version, raw_user_id, product_code, market, signature = payload.split(":")
        user_id = int(raw_user_id)
    except (ValueError, AttributeError):
        return None
    if version != "v2" or user_id != expected_user_id or product_code not in PRODUCTS or market not in MARKETS:
        return None
    body = f"{version}:{user_id}:{product_code}:{market}"
    signing_secret = settings.payment_secret or settings.bot_token
    expected = hmac.new(signing_secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    if not hmac.compare_digest(signature, expected):
        return None
    return PRODUCTS[product_code], market


def paywall_text(lang: str, market: str) -> str:
    prices = {code: price(market, code) for code in PRODUCTS}
    if lang == "ru":
        return (
            "<b>Выбери Premium</b>\n\n"
            f"<b>Plus · {prices['plus']} ⭐/мес</b>\n100 сообщений в день · память 30 фактов\n\n"
            f"<b>Pro · {prices['pro']} ⭐/мес — рекомендуем</b>\n300 сообщений · умнее модель · память 100 фактов\n\n"
            f"<b>Ultra · {prices['ultra']} ⭐/мес</b>\n800 сообщений · лучшая модель · память 250 фактов\n\n"
            f"<b>Black · {prices['black']} ⭐ за год</b>\nВозможности Ultra на 365 дней одним платежом."
        )
    if lang == "uk":
        return (
            "<b>Обери Premium</b>\n\n"
            f"<b>Plus · {prices['plus']} ⭐/міс</b>\n100 повідомлень на день · пам'ять 30 фактів\n\n"
            f"<b>Pro · {prices['pro']} ⭐/міс — рекомендуємо</b>\n300 повідомлень · розумніша модель · пам'ять 100 фактів\n\n"
            f"<b>Ultra · {prices['ultra']} ⭐/міс</b>\n800 повідомлень · найкраща модель · пам'ять 250 фактів\n\n"
            f"<b>Black · {prices['black']} ⭐ за рік</b>\nМожливості Ultra на 365 днів одним платежем."
        )
    if lang == "es":
        return (
            "<b>Elige Premium</b>\n\n"
            f"<b>Plus · {prices['plus']} ⭐/mes</b>\n100 mensajes al día · 30 recuerdos\n\n"
            f"<b>Pro · {prices['pro']} ⭐/mes — recomendado</b>\n300 mensajes · mejor modelo · 100 recuerdos\n\n"
            f"<b>Ultra · {prices['ultra']} ⭐/mes</b>\n800 mensajes · modelo superior · 250 recuerdos\n\n"
            f"<b>Black · {prices['black']} ⭐ por un año</b>\nUltra durante 365 días con un solo pago."
        )
    if lang == "de":
        return (
            "<b>Wähle Premium</b>\n\n"
            f"<b>Plus · {prices['plus']} ⭐/Monat</b>\n100 Nachrichten täglich · 30 Erinnerungen\n\n"
            f"<b>Pro · {prices['pro']} ⭐/Monat — empfohlen</b>\n300 Nachrichten · besseres Modell · 100 Erinnerungen\n\n"
            f"<b>Ultra · {prices['ultra']} ⭐/Monat</b>\n800 Nachrichten · bestes Modell · 250 Erinnerungen\n\n"
            f"<b>Black · {prices['black']} ⭐ für ein Jahr</b>\nUltra für 365 Tage mit einer Zahlung."
        )
    if lang == "fr":
        return (
            "<b>Choisis Premium</b>\n\n"
            f"<b>Plus · {prices['plus']} ⭐/mois</b>\n100 messages par jour · 30 souvenirs\n\n"
            f"<b>Pro · {prices['pro']} ⭐/mois — recommandé</b>\n300 messages · meilleur modèle · 100 souvenirs\n\n"
            f"<b>Ultra · {prices['ultra']} ⭐/mois</b>\n800 messages · modèle supérieur · 250 souvenirs\n\n"
            f"<b>Black · {prices['black']} ⭐ pour un an</b>\nUltra pendant 365 jours en un paiement."
        )
    return (
        "<b>Choose Premium</b>\n\n"
        f"<b>Plus · {prices['plus']} ⭐/month</b>\n100 messages/day · 30 long-term memories\n\n"
        f"<b>Pro · {prices['pro']} ⭐/month — recommended</b>\n300 messages · smarter model · 100 memories\n\n"
        f"<b>Ultra · {prices['ultra']} ⭐/month</b>\n800 messages · best model · 250 memories\n\n"
        f"<b>Black · {prices['black']} ⭐ for one year</b>\nUltra access for 365 days with one payment."
    )
