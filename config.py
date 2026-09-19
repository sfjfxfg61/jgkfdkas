from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_id: int = _int("ADMIN_ID", 0)
    port: int = _int("PORT", 8080)
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    ai_model: str = os.getenv("GROQ_MODEL", os.getenv("AI_MODEL", "openai/gpt-oss-20b"))
    pro_ai_model: str = os.getenv("PRO_AI_MODEL", "openai/gpt-oss-20b")
    ultra_ai_model: str = os.getenv("ULTRA_AI_MODEL", "qwen/qwen3.8-27b")
    fallback_ai_model: str = os.getenv("GROQ_FALLBACK_MODEL", "qwen/qwen3.8-27b")
    ai_timeout_seconds: int = _int("AI_TIMEOUT_SECONDS", 30)
    payment_secret: str = os.getenv("PAYMENT_SECRET", "")
    companion_name: str = "Vika"
    memory_extraction_interval: int = _int("MEMORY_EXTRACTION_INTERVAL", 12)
    human_takeover_minutes: int = _int("HUMAN_TAKEOVER_MINUTES", 30)
    private_channel_url: str = os.getenv("PRIVATE_CHANNEL_URL", "").strip()
    pub_link_uk: str = os.getenv("PUB_LINK_UK", "").strip()
    pub_link_ru: str = os.getenv("PUB_LINK_RU", "").strip()
    pub_link_en: str = os.getenv("PUB_LINK_EN", "").strip()
    pub_link_es: str = os.getenv("PUB_LINK_ES", "").strip()
    pub_link_de: str = os.getenv("PUB_LINK_DE", "").strip()
    pub_link_fr: str = os.getenv("PUB_LINK_FR", "").strip()

    def public_channel(self, lang: str) -> str:
        links = {
            "uk": self.pub_link_uk,
            "ru": self.pub_link_ru,
            "en": self.pub_link_en,
            "es": self.pub_link_es,
            "de": self.pub_link_de,
            "fr": self.pub_link_fr,
        }
        return links.get(lang) or self.pub_link_en

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("BOT_TOKEN", self.bot_token),
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_KEY", self.supabase_key),
                ("GROQ_API_KEY", self.groq_api_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


settings = Settings()
