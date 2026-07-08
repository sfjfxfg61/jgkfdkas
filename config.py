import os
import logging

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    raise RuntimeError("Критические переменные окружения (BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY) не заданы!")

# Ссылки на твои открытые каналы для каждой локали
PUBLIC_CHANNELS = {
    "uk": os.getenv("PUB_LINK_UK", "https://t.me/your_pub_uk"),
    "ru": os.getenv("PUB_LINK_RU", "https://t.me/your_pub_ru"),
    "en": os.getenv("PUB_LINK_EN", "https://t.me/your_pub_en"),
    "de": os.getenv("PUB_LINK_DE", "https://t.me/your_pub_de"),
    "fr": os.getenv("PUB_LINK_FR", "https://t.me/your_pub_fr"),
    "es": os.getenv("PUB_LINK_ES", "https://t.me/your_pub_es"),
}

# Ссылка на финальную приватку (выдается после оплаты)
PRIVATE_CHANNEL_URL = os.getenv("PRIVATE_CHANNEL_URL", "https://t.me/+your_private_link")
