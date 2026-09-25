from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from config import settings


SUBSCRIPTION_PERIOD = 2_592_000
MARKETS = {"ua", "cis", "latam", "eu", "us", "global"}


@dataclass(frozen=True, slots=True)
class Entitlements:
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
        duration_days=30,
        recurring=True,
        title="Private + Calls",
        badge="HIGH VALUE",
    ),
}


PRODUCT_TITLES: dict[str, dict[str, str]] = {
    "ru": {
        "plus": "Закрытый канал", "pro": "Канал + чат", "ultra": "Канал + приоритет", "black": "Личный формат",
    },
    "uk": {
        "plus": "Приватний канал", "pro": "Канал + чат", "ultra": "Канал + пріоритет", "black": "Особистий формат",
    },
    "en": {
        "plus": "Private channel", "pro": "Channel + chat", "ultra": "Channel + priority", "black": "Personal format",
    },
    "es": {
        "plus": "Canal privado", "pro": "Canal + chat", "ultra": "Canal + prioridad", "black": "Atención personal",
    },
    "de": {
        "plus": "Privater Kanal", "pro": "Kanal + Chat", "ultra": "Kanal + Priorität", "black": "Persönliches Angebot",
    },
    "fr": {
        "plus": "Canal privé", "pro": "Canal + chat", "ultra": "Canal + priorité", "black": "Accompagnement personnel",
    },
}


ENTITLEMENTS: dict[str, Entitlements] = {
    "free": Entitlements(
        12,
        10,
        settings.ai_model,
        False,
    ),
    "plus": Entitlements(
        30,
        30,
        settings.ai_model,
        True,
    ),
    "pro": Entitlements(
        60,
        100,
        settings.pro_ai_model,
        True,
    ),
    "ultra": Entitlements(
        100,
        250,
        settings.ultra_ai_model,
        True,
    ),
    "black": Entitlements(
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


def invoice_description(lang: str, code: str) -> str:
    details = {
        "uk": {"plus": "Приватний канал", "pro": "Канал та особистий чат", "ultra": "Канал, чат і пріоритетні відповіді", "black": "Канал, чат, пріоритет та 2 узгоджені дзвінки по 20 хв"},
        "ru": {"plus": "Закрытый канал", "pro": "Канал и личный чат", "ultra": "Канал, чат и приоритетные ответы", "black": "Канал, чат, приоритет и 2 согласованных звонка по 20 мин"},
        "en": {"plus": "Private channel", "pro": "Channel and personal chat", "ultra": "Channel, chat and priority replies", "black": "Channel, chat, priority and 2 scheduled 20-minute calls"},
        "es": {"plus": "Canal privado", "pro": "Canal y chat personal", "ultra": "Canal, chat y respuestas prioritarias", "black": "Canal, chat, prioridad y 2 llamadas de 20 minutos"},
        "de": {"plus": "Privater Kanal", "pro": "Kanal und persönlicher Chat", "ultra": "Kanal, Chat und bevorzugte Antworten", "black": "Kanal, Chat, Priorität und 2 Anrufe à 20 Minuten"},
        "fr": {"plus": "Canal privé", "pro": "Canal et chat personnel", "ultra": "Canal, chat et réponses prioritaires", "black": "Canal, chat, priorité et 2 appels de 20 minutes"},
    }
    return details.get(lang, details["en"])[code]


def billing_period_text(lang: str) -> str:
    return {
        "uk": "30 днів; автоматичне продовження кожні 30 днів",
        "ru": "30 дней; автоматическое продление каждые 30 дней",
        "en": "30 days; renews automatically every 30 days",
        "es": "30 días; renovación automática cada 30 días",
        "de": "30 Tage; automatische Verlängerung alle 30 Tage",
        "fr": "30 jours ; renouvellement automatique tous les 30 jours",
    }.get(lang, "30 days; renews automatically every 30 days")


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
    copy = {
        "uk": ("Доступ на 30 днів", "Приватний канал із готовим контентом", "Канал і особистий чат", "Канал, чат і пріоритетні відповіді", "Усе вище та два узгоджені дзвінки по 20 хвилин (/call)", "Оплата повторюється кожні 30 днів. Продовження можна скасувати."),
        "ru": ("Доступ на 30 дней", "Закрытый канал с готовым контентом", "Канал и личный чат", "Канал, чат и приоритетные ответы", "Всё выше и два согласованных звонка по 20 минут", "Оплата повторяется каждые 30 дней. Продление можно отменить."),
        "en": ("30-day access", "Private channel with existing content", "Channel and personal chat", "Channel, chat and priority replies", "All of the above and two scheduled 20-minute calls", "Renews every 30 days. You can cancel renewal."),
        "es": ("Acceso por 30 días", "Canal privado con contenido disponible", "Canal y chat personal", "Canal, chat y respuestas prioritarias", "Todo lo anterior y dos llamadas acordadas de 20 minutos", "Renovación cada 30 días; puedes cancelarla."),
        "de": ("Zugang für 30 Tage", "Privater Kanal mit vorhandenen Inhalten", "Kanal und persönlicher Chat", "Kanal, Chat und bevorzugte Antworten", "Alles oben Genannte und zwei vereinbarte Anrufe à 20 Minuten", "Verlängert sich alle 30 Tage; kündbar."),
        "fr": ("Accès de 30 jours", "Canal privé avec contenu existant", "Canal et chat personnel", "Canal, chat et réponses prioritaires", "Tout cela et deux appels convenus de 20 minutes", "Renouvellement tous les 30 jours ; résiliation possible."),
    }.get(lang, ())
    title, *items, renewal = copy or ("30-day access", "Private channel", "Channel and chat", "Priority replies", "Two scheduled calls", "Renews every 30 days")
    lines = [f"<b>{title}</b>"]
    for icon, code, detail in zip(("⚡", "🔥", "🚀", "💎"), PRODUCTS, items):
        lines.append(f"{icon} <b>{product_title(lang, code)} · {price(market, code)} ⭐</b>\n{detail}")
    return "\n\n".join(lines) + f"\n\n{renewal}"
