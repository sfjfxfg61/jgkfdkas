from __future__ import annotations

import base64
import json
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


def _jwt_role(value: str) -> str | None:
    """Best-effort role detection for legacy Supabase JWT keys."""
    try:
        parts = value.split(".")
        if len(parts) != 3:
            return None
        raw = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(raw.encode()).decode())
        role = payload.get("role")
        return str(role) if role else None
    except Exception:
        return None


def _looks_like_public_supabase_key(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    if value.startswith("sb_publishable_"):
        return True
    return _jwt_role(value) in {"anon", "authenticated"}


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
    invoice_signing_key: str = os.getenv("INVOICE_SIGNING_KEY") or os.getenv("BOT_TOKEN", "")
    legacy_invoice_signing_key: str = os.getenv("LEGACY_INVOICE_SIGNING_KEY", "")
    state_dir: str = os.getenv("STATE_DIR", "./state")
    admin_id: int = _int("ADMIN_ID", 0)
    port: int = _int("PORT", 8080)
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    # Prefer an explicit server-side secret when present. Existing deployments can
    # keep SUPABASE_KEY, but it must be a service-role / sb_secret key.
    supabase_key: str = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")).strip()

    companion_name: str = os.getenv("COMPANION_NAME", "Vika").strip() or "Vika"
    followups_enabled: bool = _bool("FOLLOWUPS_ENABLED", True)
    marketing_mode: str = os.getenv("MARKETING_MODE", "limited").strip().lower()

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

    @property
    def supabase_key_kind(self) -> str:
        if self.supabase_key.startswith("sb_secret_"):
            return "secret"
        if self.supabase_key.startswith("sb_publishable_"):
            return "publishable"
        return _jwt_role(self.supabase_key) or "unknown"

    def validate(self) -> None:
        if self.marketing_mode not in {"limited", "legacy"}:
            raise RuntimeError("MARKETING_MODE must be limited or legacy")
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
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
        if _looks_like_public_supabase_key(self.supabase_key):
            raise RuntimeError(
                "SUPABASE_KEY is an anon/publishable key. This bot needs the server-side "
                "Supabase service_role (legacy JWT) or sb_secret_ key because automation_jobs "
                "and pending_replies use RLS. Replace SUPABASE_KEY on Render, or set "
                "SUPABASE_SERVICE_ROLE_KEY."
            )


settings = Settings()
