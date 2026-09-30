from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from config import settings

SUBSCRIPTION_PERIOD = 2_592_000  # 30 days, Telegram Stars recurring subscription period
CHECKOUT_TTL_SECONDS = 86_400  # each generated payment link is valid for 24 hours
MARKETS = {"ua", "cis", "latam", "eu", "us", "global"}


@dataclass(frozen=True, slots=True)
class Product:
    code: str
    tier: str
    duration_days: int
    recurring: bool
    title: str


# Keep these internal codes for compatibility with existing payments/users.
PRODUCTS: dict[str, Product] = {
    "plus": Product("plus", "plus", 30, True, "Private channel"),
    "pro": Product("pro", "pro", 30, True, "Channel + chat"),
    "ultra": Product("ultra", "ultra", 30, True, "Channel + priority"),
    "black": Product("black", "black", 30, True, "Personal format"),
}

PRODUCT_TITLES: dict[str, dict[str, str]] = {
    "uk": {"plus": "Приватний канал", "pro": "Канал + чат", "ultra": "Канал + пріоритет", "black": "Особистий формат"},
    "ru": {"plus": "Приватный канал", "pro": "Канал + чат", "ultra": "Канал + приоритет", "black": "Личный формат"},
    "en": {"plus": "Private channel", "pro": "Channel + chat", "ultra": "Channel + priority", "black": "Personal format"},
    "de": {"plus": "Privater Kanal", "pro": "Kanal + Chat", "ultra": "Kanal + Priorität", "black": "Persönliches Format"},
    "fr": {"plus": "Canal privé", "pro": "Canal + chat", "ultra": "Canal + priorité", "black": "Formule personnelle"},
    "es": {"plus": "Canal privado", "pro": "Canal + chat", "ultra": "Canal + prioridad", "black": "Formato personal"},
}

# Current regional pricing. Change only these numbers to update prices.
PRICE_MATRIX: dict[str, dict[str, int]] = {
    "ua": {"plus": 249, "pro": 549, "ultra": 1_299, "black": 4_999},
    "cis": {"plus": 299, "pro": 699, "ultra": 1_499, "black": 5_499},
    "latam": {"plus": 349, "pro": 799, "ultra": 1_799, "black": 5_999},
    "eu": {"plus": 599, "pro": 1_399, "ultra": 3_299, "black": 8_499},
    "us": {"plus": 899, "pro": 2_199, "ultra": 4_999, "black": 9_999},
    "global": {"plus": 499, "pro": 1_099, "ultra": 2_499, "black": 6_999},
}


def product_title(lang: str, product_code: str) -> str:
    return PRODUCT_TITLES.get(lang, PRODUCT_TITLES["en"]).get(product_code, PRODUCTS[product_code].title)


def product_description(lang: str, code: str) -> str:
    copy = {
        "uk": {
            "plus": "Приватний канал з усім доступним контентом",
            "pro": "Приватний канал та особистий чат",
            "ultra": "Канал, особистий чат і пріоритетні відповіді",
            "black": "Усе вище та два узгоджені дзвінки по 20 хвилин",
        },
        "ru": {
            "plus": "Приватный канал со всем доступным контентом",
            "pro": "Приватный канал и личный чат",
            "ultra": "Канал, личный чат и приоритетные ответы",
            "black": "Всё выше и два согласованных звонка по 20 минут",
        },
        "en": {
            "plus": "Private channel with all available content",
            "pro": "Private channel and personal chat",
            "ultra": "Channel, personal chat and priority replies",
            "black": "Everything above and two scheduled 20-minute calls",
        },
        "de": {
            "plus": "Privater Kanal mit allen verfügbaren Inhalten",
            "pro": "Privater Kanal und persönlicher Chat",
            "ultra": "Kanal, persönlicher Chat und bevorzugte Antworten",
            "black": "Alles oben Genannte und zwei vereinbarte 20-Minuten-Anrufe",
        },
        "fr": {
            "plus": "Canal privé avec tout le contenu disponible",
            "pro": "Canal privé et chat personnel",
            "ultra": "Canal, chat personnel et réponses prioritaires",
            "black": "Tout cela et deux appels convenus de 20 minutes",
        },
        "es": {
            "plus": "Canal privado con todo el contenido disponible",
            "pro": "Canal privado y chat personal",
            "ultra": "Canal, chat personal y respuestas prioritarias",
            "black": "Todo lo anterior y dos llamadas acordadas de 20 minutos",
        },
    }
    return copy.get(lang, copy["en"])[code]


def billing_period_text(lang: str) -> str:
    return {
        "uk": "30 днів · автоматичне продовження кожні 30 днів",
        "ru": "30 дней · автоматическое продление каждые 30 дней",
        "en": "30 days · renews automatically every 30 days",
        "de": "30 Tage · automatische Verlängerung alle 30 Tage",
        "fr": "30 jours · renouvellement automatique tous les 30 jours",
        "es": "30 días · renovación automática cada 30 días",
    }.get(lang, "30 days · renews automatically every 30 days")


def default_market(lang: str, ref: str = "") -> str:
    del ref
    return {"uk": "ua", "ru": "cis", "es": "latam", "de": "eu", "fr": "eu", "en": "us"}.get(lang, "global")


def price(market: str, product_code: str) -> int:
    safe_market = market if market in PRICE_MATRIX else "global"
    if product_code not in PRODUCTS:
        raise ValueError(f"Unknown product: {product_code}")
    return PRICE_MATRIX[safe_market][product_code]


def make_payload(
    user_id: int,
    product_code: str,
    market: str,
    *,
    expires_at: int | None = None,
) -> str:
    """Create a signed Telegram Stars payload with a real 24h checkout deadline.

    Legacy v2-v4 payloads are still accepted by parse_payload so already-created
    payment links from the previous production version keep working.
    """
    if product_code not in PRODUCTS or market not in MARKETS:
        raise ValueError("Unknown product or market")
    expiry = int(expires_at or (time.time() + CHECKOUT_TTL_SECONDS))
    body = f"v5:{user_id}:{product_code}:{market}:{expiry}"
    signature = hmac.new(settings.bot_token.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{body}:{signature}"


def parse_payload(
    payload: str,
    expected_user_id: int,
    *,
    allow_expired: bool = False,
) -> tuple[Product, str] | None:
    try:
        parts = payload.split(":")
        version = parts[0]
        if version == "v5":
            if len(parts) != 6:
                return None
            _, raw_user_id, product_code, market, raw_expiry, signature = parts
            expiry = int(raw_expiry)
            body = f"v5:{raw_user_id}:{product_code}:{market}:{raw_expiry}"
        else:
            if len(parts) != 5:
                return None
            _, raw_user_id, product_code, market, signature = parts
            expiry = None
            body = f"{version}:{raw_user_id}:{product_code}:{market}"
        user_id = int(raw_user_id)
    except (ValueError, AttributeError, IndexError):
        return None

    if version not in {"v2", "v3", "v4", "v5"}:
        return None
    if user_id != expected_user_id or product_code not in PRODUCTS or market not in MARKETS:
        return None

    expected = hmac.new(settings.bot_token.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    if not hmac.compare_digest(signature, expected):
        return None
    if version == "v5" and not allow_expired and expiry is not None and int(time.time()) > expiry:
        return None
    return PRODUCTS[product_code], market


def paywall_text(lang: str, market: str) -> str:
    intro = {
        "uk": "<b>Хочеш ближче? Обирай формат 💕</b>\n\nЯ зробила кілька варіантів — від просто привату до особистого формату:",
        "ru": "<b>Хочешь ближе? Выбирай формат 💕</b>\n\nЯ сделала несколько вариантов — от просто привата до личного формата:",
        "en": "<b>Want a little more? Pick your format 💕</b>\n\nI made a few options — from the private channel to a more personal format:",
        "de": "<b>Du willst etwas mehr? Wähle dein Format 💕</b>\n\nIch habe ein paar Varianten gemacht — vom privaten Kanal bis zum persönlicheren Format:",
        "fr": "<b>Tu veux un peu plus ? Choisis ta formule 💕</b>\n\nJ'ai préparé plusieurs options — du canal privé à une formule plus personnelle :",
        "es": "<b>¿Quieres un poco más? Elige tu formato 💕</b>\n\nPreparé varias opciones — desde el canal privado hasta un formato más personal:",
    }.get(lang, "<b>Choose your format 💕</b>")
    renewal = {
        "uk": "\n\n<i>Оплата в Telegram Stars. Підписка продовжується кожні 30 днів; продовження можна вимкнути в боті.</i>",
        "ru": "\n\n<i>Оплата в Telegram Stars. Подписка продлевается каждые 30 дней; продление можно отключить в боте.</i>",
        "en": "\n\n<i>Payment is in Telegram Stars. It renews every 30 days; renewal can be turned off in the bot.</i>",
        "de": "\n\n<i>Zahlung mit Telegram Stars. Verlängerung alle 30 Tage; die Verlängerung kann im Bot ausgeschaltet werden.</i>",
        "fr": "\n\n<i>Paiement en Telegram Stars. Renouvellement tous les 30 jours ; il peut être désactivé dans le bot.</i>",
        "es": "\n\n<i>Pago con Telegram Stars. Se renueva cada 30 días; puedes desactivar la renovación en el bot.</i>",
    }.get(lang, "")
    icons = {"plus": "💎", "pro": "💌", "ultra": "👑", "black": "🖤"}
    lines = [intro]
    for code in PRODUCTS:
        lines.append(
            f"{icons[code]} <b>{product_title(lang, code)} — {price(market, code)} ⭐</b>\n"
            f"{product_description(lang, code)}"
        )
    return "\n\n".join(lines) + renewal
