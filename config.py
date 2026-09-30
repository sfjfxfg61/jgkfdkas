from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def telegram_chat_ref(raw: str | None) -> int | str | None:
    """Convert a Telegram numeric id, @username or public t.me link to Bot API chat ref.

    Public links like https://t.me/example become @example. Invite links t.me/+... cannot
    be used for getChatMember and therefore return None.
    """
    value = (raw or "").strip()
    if not value:
        return None
    if value.lstrip("-").isdigit():
        return int(value)
    if value.startswith("@") and value[1:].replace("_", "").isalnum():
        return value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    if parsed.hostname not in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
        return None
    path = parsed.path.strip("/")
    if path.startswith("c/"):
        parts = path.split("/")
        if len(parts) >= 2 and parts[1].isdigit():
            return int("-100" + parts[1])
    if path and not path.startswith("+") and "/" not in path and path.replace("_", "").isalnum():
        return "@" + path
    return None


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_id: int = _int("ADMIN_ID", 0)
    port: int = _int("PORT", 8080)
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")

    companion_name: str = os.getenv("COMPANION_NAME", "Vika").strip() or "Vika"
    followups_enabled: bool = _bool("FOLLOWUPS_ENABLED", True)

    # Compatibility switch. Production is expected to keep this false. If enabled,
    # AI is used ONLY as a delayed reply writer; there is no XP, memory or relationship system.
    auto_reply_ai: bool = _bool("AUTO_REPLY_AI", False)
    auto_reply_delay_minutes: int = _int("HUMAN_TAKEOVER_MINUTES", 30)
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    groq_fallback_model: str = os.getenv("GROQ_FALLBACK_MODEL", "")
    ai_timeout_seconds: int = _int("AI_TIMEOUT_SECONDS", 30)

    private_channel_url: str = (os.getenv("PRIVATE_CHANNEL_ID") or os.getenv("PRIVATE_CHANNEL_URL", "")).strip()

    pub_link_uk: str = os.getenv("PUB_LINK_UK", "").strip()
    pub_link_ru: str = os.getenv("PUB_LINK_RU", "").strip()
    pub_link_en: str = os.getenv("PUB_LINK_EN", "").strip()
    pub_link_es: str = os.getenv("PUB_LINK_ES", "").strip()
    pub_link_de: str = os.getenv("PUB_LINK_DE", "").strip()
    pub_link_fr: str = os.getenv("PUB_LINK_FR", "").strip()

    @property
    def private_channel_ref(self) -> int | str | None:
        return telegram_chat_ref(self.private_channel_url)

    def public_channel(self, lang: str) -> str:
        links = {
            "uk": self.pub_link_uk,
            "ru": self.pub_link_ru,
            "en": self.pub_link_en,
            "es": self.pub_link_es,
            "de": self.pub_link_de,
            "fr": self.pub_link_fr,
        }
        return links.get(lang) or self.pub_link_en or self.pub_link_ru or self.pub_link_uk

    def public_channel_ref(self, lang: str) -> int | str | None:
        return telegram_chat_ref(self.public_channel(lang))

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("BOT_TOKEN", self.bot_token),
                ("ADMIN_ID", self.admin_id),
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_KEY", self.supabase_key),
            )
            if not value
        ]
        if self.auto_reply_ai and not self.groq_api_key:
            missing.append("GROQ_API_KEY (only required when AUTO_REPLY_AI=true)")
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


settings = Settings()
