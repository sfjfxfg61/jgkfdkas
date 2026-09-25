from __future__ import annotations

from datetime import datetime, timezone

SUPPORTED_LANGS = {"ru", "uk", "en", "es", "de", "fr"}
STYLES = {"warm", "playful", "calm"}


def normalize_lang(language_code: str | None) -> str:
    if not language_code:
        return "en"
    lang = language_code.lower()[:2]
    return lang if lang in SUPPORTED_LANGS else "en"


def normalize_style(style: str | None) -> str:
    return style if style in STYLES else "warm"


def premium_is_active(user: dict, now: datetime | None = None) -> bool:
    if not user.get("is_premium") or not user.get("premium_until"):
        return False
    try:
        expires = datetime.fromisoformat(str(user["premium_until"]).replace("Z", "+00:00"))
    except ValueError:
        return False
    return expires > (now or datetime.now(timezone.utc))


def relationship_level(xp: int) -> tuple[int, str]:
    levels = ((0, "new"), (80, "familiar"), (250, "close"), (600, "trusted"))
    index = 0
    for i, (threshold, _) in enumerate(levels):
        if xp >= threshold:
            index = i
    return index + 1, levels[index][1]


def compact_text(value: str, limit: int = 4000) -> str:
    return " ".join(value.strip().split())[:limit]
