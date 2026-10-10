from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from config import settings

SUBSCRIPTION_PERIOD = 2_592_000  # 30 days, Telegram Stars recurring subscription period
CHECKOUT_TTL_SECONDS = 86_400  # each generated payment link is valid for 24 hours
MARKETS = {"ua", "cis", "latam", "asia", "eu", "us", "global"}


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

# Prices match one-purchase Telegram Stars packs shown in the owner's checkout.
# Confirm actual available packages separately for each user's platform/region.
PRICE_MATRIX: dict[str, dict[str, int]] = {
    "ua": {"plus": 150, "pro": 350, "ultra": 750, "black": 2_500},
    "cis": {"plus": 150, "pro": 350, "ultra": 750, "black": 2_500},
    "latam": {"plus": 150, "pro": 350, "ultra": 750, "black": 2_500},
    "asia": {"plus": 150, "pro": 350, "ultra": 750, "black": 2_500},
    "eu": {"plus": 250, "pro": 500, "ultra": 1_000, "black": 2_500},
    "us": {"plus": 250, "pro": 500, "ultra": 1_000, "black": 2_500},
    "global": {"plus": 250, "pro": 500, "ultra": 1_000, "black": 2_500},
}

# Do not change: paid invoices/recurring subscriptions from the old deployment
# must still validate at their originally billed amount after price changes.
LEGACY_PRICE_MATRIX: dict[str, dict[str, int]] = {
    "ua": {"plus": 249, "pro": 549, "ultra": 1_299, "black": 4_999},
    "cis": {"plus": 299, "pro": 699, "ultra": 1_499, "black": 5_499},
    "latam": {"plus": 349, "pro": 799, "ultra": 1_799, "black": 5_999},
    # No historical Asia-specific pricing existed. Keep a defensive fallback
    # so legacy payload parsing cannot raise for this market.
    "asia": {"plus": 150, "pro": 350, "ultra": 750, "black": 2_500},
    "eu": {"plus": 599, "pro": 1_399, "ultra": 3_299, "black": 8_499},
    "us": {"plus": 899, "pro": 2_199, "ultra": 4_999, "black": 9_999},
    "global": {"plus": 499, "pro": 1_099, "ultra": 2_499, "black": 6_999},
}


@dataclass(frozen=True, slots=True)
class PaymentDetails:
    product: Product
    market: str
    amount: int | None
    version: str


def amount_matches_invoice(details: PaymentDetails, amount: int) -> bool:
    """Verify a checkout without invalidating signed historical invoices."""
    if not isinstance(amount, int) or amount <= 0:
        return False
    if details.amount is not None:
        return details.amount == amount
    return amount in {
        PRICE_MATRIX[details.market][details.product.code],
        LEGACY_PRICE_MATRIX[details.market][details.product.code],
    }


def product_title(lang: str, product_code: str) -> str:
    return PRODUCT_TITLES.get(lang, PRODUCT_TITLES["en"]).get(product_code, PRODUCTS[product_code].title)


def product_description(lang: str, code: str) -> str:
    copy = {
        "uk": {
            "plus": "Приватний канал з усім доступним контентом",
            "pro": "Приватний канал та особистий чат",
            "ultra": "Канал, особистий чат і пріоритетні відповіді",
            "black": "Усе вище та доступ до відеодзвінків за попереднім узгодженням",
        },
        "ru": {
            "plus": "Приватный канал со всем доступным контентом",
            "pro": "Приватный канал и личный чат",
            "ultra": "Канал, личный чат и приоритетные ответы",
            "black": "Всё выше и доступ к видеозвонкам по предварительному согласованию",
        },
        "en": {
            "plus": "Private channel with all available content",
            "pro": "Private channel and personal chat",
            "ultra": "Channel, personal chat and priority replies",
            "black": "Everything above and access to video calls by prior arrangement",
        },
        "de": {
            "plus": "Privater Kanal mit allen verfügbaren Inhalten",
            "pro": "Privater Kanal und persönlicher Chat",
            "ultra": "Kanal, persönlicher Chat und bevorzugte Antworten",
            "black": "Alles oben Genannte und Zugang zu Videoanrufen nach vorheriger Absprache",
        },
        "fr": {
            "plus": "Canal privé avec tout le contenu disponible",
            "pro": "Canal privé et chat personnel",
            "ultra": "Canal, chat personnel et réponses prioritaires",
            "black": "Tout cela et accès aux appels vidéo sur rendez-vous",
        },
        "es": {
            "plus": "Canal privado con todo el contenido disponible",
            "pro": "Canal privado y chat personal",
            "ultra": "Canal, chat personal y respuestas prioritarias",
            "black": "Todo lo anterior y acceso a videollamadas previo acuerdo",
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
    """Never infer the customer's location from Telegram language or referral."""
    del lang, ref
    return "global"


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
    """Sign the exact invoiced Stars amount so later price changes are safe."""
    if product_code not in PRODUCTS or market not in MARKETS:
        raise ValueError("Unknown product or market")
    expiry = int(expires_at or (time.time() + CHECKOUT_TTL_SECONDS))
    amount = price(market, product_code)
    body = f"v6:{user_id}:{product_code}:{market}:{amount}:{expiry}"
    signature = hmac.new(settings.invoice_signing_key.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{body}:{signature}"


def parse_payment_details(
    payload: str,
    expected_user_id: int,
    *,
    allow_expired: bool = False,
) -> PaymentDetails | None:
    """Read signed v2-v6 payments, including existing recurring subscriptions."""
    try:
        parts = payload.split(":")
        version = parts[0]
        if version == "v6":
            if len(parts) != 7:
                return None
            _, raw_user_id, product_code, market, raw_amount, raw_expiry, signature = parts
            amount = int(raw_amount)
            expiry = int(raw_expiry)
            body = ":".join(parts[:-1])
            if amount <= 0:
                return None
        elif version == "v5":
            if len(parts) != 6:
                return None
            _, raw_user_id, product_code, market, raw_expiry, signature = parts
            expiry = int(raw_expiry)
            amount = None
            body = ":".join(parts[:-1])
        elif version in {"v2", "v3", "v4"}:
            if len(parts) != 5:
                return None
            _, raw_user_id, product_code, market, signature = parts
            expiry, amount = None, None
            body = ":".join(parts[:-1])
        else:
            return None
        user_id = int(raw_user_id)
    except (ValueError, AttributeError, IndexError):
        return None

    if user_id != expected_user_id or product_code not in PRODUCTS or market not in MARKETS:
        return None
    current_valid = hmac.compare_digest(signature, hmac.new(settings.invoice_signing_key.encode(), body.encode(), hashlib.sha256).hexdigest()[:20])
    legacy_valid = bool(allow_expired and settings.legacy_invoice_signing_key and
        hmac.compare_digest(signature, hmac.new(settings.legacy_invoice_signing_key.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]))
    if not current_valid and not legacy_valid:
        return None
    # A disclosed legacy key must never authorize new checkout or arbitrary signed prices.
    if legacy_valid and not current_valid and amount is not None and amount not in {
            PRICE_MATRIX[market][product_code], LEGACY_PRICE_MATRIX[market][product_code]}:
        return None
    if version in {"v5", "v6"} and not allow_expired and int(time.time()) > expiry:
        return None
    return PaymentDetails(PRODUCTS[product_code], market, amount, version)


def parse_payload(
    payload: str,
    expected_user_id: int,
    *,
    allow_expired: bool = False,
) -> tuple[Product, str] | None:
    """Backwards-compatible public API for existing code and tests."""
    details = parse_payment_details(payload, expected_user_id, allow_expired=allow_expired)
    return (details.product, details.market) if details else None


def paywall_text(lang: str, market: str) -> str:
    intros = {
        "uk": "<b>Підписка Victoria 💕</b>",
        "ru": "<b>Подписка Victoria 💕</b>",
        "en": "<b>Victoria plans 💕</b>",
        "de": "<b>Victoria Abos 💕</b>",
        "fr": "<b>Abonnements Victoria 💕</b>",
        "es": "<b>Suscripciones Victoria 💕</b>",
    }
    icons = {"plus": "💎", "pro": "💌", "ultra": "👑", "black": "🖤"}
    lines = [intros.get(lang, intros["en"])]
    for code in PRODUCTS:
        lines.append(f"{icons[code]} <b>{product_title(lang, code)}</b> — {price(market, code)} ⭐\n{product_description(lang, code)}")
    renewal = {
        "uk": "<i>30 днів · автопродовження кожні 30 днів; можна вимкнути в боті.</i>",
        "ru": "<i>30 дней · автопродление каждые 30 дней; можно отключить в боте.</i>",
        "en": "<i>30 days · auto-renews every 30 days; you can cancel renewal in the bot.</i>",
        "de": "<i>30 Tage · automatische Verlängerung; im Bot kündbar.</i>",
        "fr": "<i>30 jours · renouvellement automatique ; résiliable dans le bot.</i>",
        "es": "<i>30 días · renovación automática; se puede cancelar en el bot.</i>",
    }
    lines.append(renewal.get(lang, renewal["en"]))
    return "\n\n".join(lines)
