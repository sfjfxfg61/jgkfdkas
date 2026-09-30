from __future__ import annotations

from datetime import datetime, timezone

SUPPORTED_LANGS = {"ru", "uk", "en", "es", "de", "fr"}


def normalize_lang(language_code: str | None) -> str:
    if not language_code:
        return "en"
    lang = language_code.lower()[:2]
    return lang if lang in SUPPORTED_LANGS else "en"


def premium_is_active(user: dict, now: datetime | None = None) -> bool:
    if not user.get("is_premium") or not user.get("premium_until"):
        return False
    try:
        expires = datetime.fromisoformat(str(user["premium_until"]).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    return expires > (now or datetime.now(timezone.utc))


def compact_text(value: str, limit: int = 4000) -> str:
    return " ".join((value or "").strip().split())[:limit]
