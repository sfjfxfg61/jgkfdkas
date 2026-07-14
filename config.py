import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    raise RuntimeError("Критические переменные окружения не заданы!")

PUBLIC_CHANNELS = {
    "uk": os.getenv("PUB_LINK_UK", "https://t.me/your_pub_uk"),
    "ru": os.getenv("PUB_LINK_RU", "https://t.me/your_pub_ru"),
    "en": os.getenv("PUB_LINK_EN", "https://t.me/your_pub_en"),
    "de": os.getenv("PUB_LINK_DE", "https://t.me/your_pub_de"),
    "fr": os.getenv("PUB_LINK_FR", "https://t.me/your_pub_fr"),
    "es": os.getenv("PUB_LINK_ES", "https://t.me/your_pub_es"),
}

PRIVATE_CHANNEL_URL = os.getenv("PRIVATE_CHANNEL_URL", "https://t.me/+your_private_link")
