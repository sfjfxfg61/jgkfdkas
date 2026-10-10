from __future__ import annotations

from datetime import datetime, timezone
import re

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


PARTNER_CODE_RE = re.compile(r"^[a-z0-9_]{3,32}$")


def normalize_partner_code(value: str | None) -> str:
    code = (value or "").strip().lower().replace("-", "_")
    if not PARTNER_CODE_RE.fullmatch(code):
        raise ValueError("Partner code must be 3-32 chars: a-z, 0-9, _")
    return code


def partner_ref(code: str) -> str:
    return f"p_{normalize_partner_code(code)}"


def partner_code_from_ref(ref: str | None) -> str | None:
    raw = (ref or "").strip().lower()
    if not raw.startswith("p_"):
        return None
    code = raw[2:]
    return code if PARTNER_CODE_RE.fullmatch(code) else None
