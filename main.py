import asyncio
import logging
import os
import re
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)

# =====================================================
# CONFIG & ENV
# =====================================================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))
PRIVATE_LINK = os.getenv("PRIVATE_CHANNEL_URL", "https://t.me/your_channel")

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing required environment variables (BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY)")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранилище запущенных тасков фоллоуапов в RAM для отмены при покупке
active_tasks = {}

# =====================================================
# SUPABASE LIGHTWEIGHT API CLIENT
# =====================================================
async def sync_user_to_db(user_id: int, username: str, first_name: str, lang: str, ref: str):
    """Сохраняет или обновляет пользователя методом UPSERT"""
    url = f"{SUPABASE_URL}/rest/v1/users"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    payload = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "lang": lang,
        "ref": ref
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in [200, 201]:
                    logging.error(f"Supabase error sync: {await resp.text()}")
        except Exception as e:
            logging.exception(f"DB Sync failed: {e}")

async def update_payment_status(user_id: int):
    """Фиксирует факт оплаты в БД"""
    url = f"{SUPABASE_URL}/rest/v1/users?user_id=eq.{user_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.patch(url, json={"is_paid": True}, headers=headers) as resp:
                if resp.status not in [200, 204]:
                    logging.error(f"Supabase error payment: {await resp.text()}")
        except Exception as e:
            logging.exception(f"DB Payment update failed: {e}")

# =====================================================
# MARKETING LOGIC & TEXTS
# =====================================================
def get_price(lang: str) -> int:
    return 500 if lang in ["uk", "ru"] else 1000

TEXTS = {
    "uk": {
        "welcome": "Привіт, {name} 🤍\n\nЯ не випадково відкрила тобі цей доступ. Тут мій приватний простір — без зайвих очей та цензури, де я ділюся тим, чого ніколи не буде у відкритому доступі.\n\nЯкщо ти тут — це твій шанс зазирнути всередину. Місця обмежені.",
        "followup_1": "Ти ще тут? 😉\n\nЯ щойно завантажила свіжий контент у приват. Зазвичай доступ відкритий лічені хвилини, щоб зберегти кулуарність. Потім вхід буде закрито.",
        "followup_2": "Я не знаю, чи ти повернешся сюди знову... 🤍\n\nАле просто зараз лінк видаляється. Якщо хочеш отримати все — забирай доступ в один клік нижче. Це остання пропозиція.",
        "btn": "✨ Отримати ексклюзивний доступ",
        "title": "Приватний простір",
        "desc": "Повний доступ до закритих матеріалів",
        "thanks": "Твій доступ підтверджено 🤍\n\nЛаскаво просимо до нашого секретного простору. Твоє персональне посилання нижче:",
    },
    "en": {
        "welcome": "Hey, {name} 🤍\n\nI didn't open this for you by accident. This is my private space — uncensored and away from prying eyes. I share things here that will never be public.\n\nIf you're here, it's your chance to look inside. Spots are limited.",
        "followup_1": "Are you still here? 😉\n\nI just uploaded brand new content to the private channel. I keep the doors open for just a few minutes to maintain exclusivity. Don't miss it.",
        "followup_2": "I don't know if you'll ever come back here... 🤍\n\nBut right now, the link is self-destructing. If you want it all — grab access below. This is your final call.",
        "btn": "✨ Get Exclusive Access",
        "title": "Private Space",
        "desc": "Full access to premium private content",
        "thanks": "Your access is verified 🤍\n\nWelcome to our secret circle. Your personal link is below:",
    },
    "ru": {
        "welcome": "Привет, {name} 🤍\n\nЯ не случайно открыла тебе этот доступ. Здесь мой приватный уголок — без лишних глаз и цензуры, где я делюсь тем, чего никогда не будет в паблике.\n\nЕсли ты здесь — это твой шанс заглянуть внутрь. Места ограничены.",
        "followup_1": "Ты ещё здесь? 😉\n\nЯ только что загрузила свежий контент в приват. Обычно доступ открыт считанные минуты, чтобы сохранить кулуарность. Потом вход будет закрыт.",
        "followup_2": "Я не знаю, вернешься ли ты сюда снова... 🤍\n\nНо прямо сейчас ссылка удаляется. Если хочешь получить всё — забирай доступ в один клик ниже. Это последнее предложение.",
        "btn": "✨ Получить эксклюзивный доступ",
        "title": "Приватное пространство",
        "desc": "Полный доступ к закрытым материалам",
        "thanks": "Твой доступ подтвержден 🤍\n\nДобро пожаловать в наше секретное пространство. Твоя персональная ссылка ниже:",
    },
    "de": {
        "welcome": "Hey, {name} 🤍\n\nIch habe diesen Zugang nicht ohne Grund für dich geöffnet. Das ist mein privater Raum — unzensiert und fernab von neugierigen Blicken.\n\nWenn du hier bist, ist das deine Chance, einen Blick hineinzuwerfen. Die Plätze sind streng limitiert.",
        "followup_1": "Bist du noch da? 😉\n\nIch habe gerade exklusive neue Inhalte hochgeladen. Ich lasse den Zugang nur für wenige Minuten offen. Nutze die Zeit.",
        "followup_2": "Ich weiß nicht, ob du jemals wiederkommst... 🤍\n\nAber genau jetzt wird der Link deaktiviert. Wenn du alles willst — sichere dir unten den Zugang. Letzte Chance.",
        "btn": "✨ Exklusiven Zugang sichern",
        "title": "Privater Raum",
        "desc": "Vollständiger Zugang zu privaten Inhalten",
        "thanks": "Dein Zugang ist bestätigt 🤍\n\nWillkommen im privaten Kreis. Dein persönlicher Link unten:",
    }
}

def get_user_lang(m: Message) -> str:
    user_lang = m.from_user.language_code
    return user_lang if user_lang in TEXTS else "en"

# =====================================================
# KEYBOARDS
# =====================================================
def main_kb(lang: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["btn"], callback_data="buy_stars")],
            [InlineKeyboardButton(text="🌐 Change Language / Сменить язык", callback_data="change_lang")]
        ]
    )

def lang_selection_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="set_lang_uk")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
            [InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="set_lang_de")]
        ]
    )

# =====================================================
# MARKETING AUTOMATION (FOLLOWUP FUNNEL)
# =====================================================
async def marketing_funnel(user_id: int, name: str, lang: str):
    try:
        # Дожим 1: через 10 минут (600 секунд)
        await asyncio.sleep(600)
        await bot.send_message(
            chat_id=user_id,
            text=TEXTS[lang]["followup_1"].format(name=name),
            reply_markup=main_kb(lang)
        )

        # Дожим 2: еще через 5 минут (300 секунд) + выставление счета автоматически
        await asyncio.sleep(300)
        await bot.send_message(chat_id=user_id, text=TEXTS[lang]["followup_2"].format(name=name))
        
        price = get_price(lang)
        await bot.send_invoice(
            chat_id=user_id,
            title=TEXTS[lang]["title"],
            description=TEXTS[lang]["desc"],
            payload=f"stars_{user_id}_{lang}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Telegram Stars", amount=price)],
            start_parameter="join_private"
        )
    except asyncio.CancelledError:
        logging.info(f"Funnel for user {user_id} cancelled due to purchase.")
    except Exception as e:
        logging.exception(f"Funnel error for {user_id}: {e}")

# =====================================================
# HANDLERS
# =====================================================
@dp.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject):
    user_id = m.from_user.id
    ref = command.args if command.args else "direct"
    lang = get_user_lang(m)
    name = m.from_user.first_name
    username = f"@{m.from_user.username}" if m.from_user.username else "None"

    # Асинхронно сохраняем в БД (без ожидания ответа для максимальной скорости бота)
    asyncio.create_task(sync_user_to_db(user_id, username, name, lang, ref))

    # Перезапускаем дожимы, если пользователь зашел заново
    if user_id in active_tasks:
        active_tasks[user_id].cancel()
    active_tasks[user_id] = asyncio.create_task(marketing_funnel(user_id, name, lang))

    await m.answer(
        text=TEXTS[lang]["welcome"].format(name=name),
        reply_markup=main_kb(lang)
    )

@dp.callback_query(F.data == "change_lang")
async def process_change_lang(c: CallbackQuery):
    await c.message.edit_text("Select your language / Выберите язык:", reply_markup=lang_selection_kb())
    await c.answer()

@dp.callback_query(F.data.startswith("set_lang_"))
async def process_set_lang(c: CallbackQuery):
    lang = c.data.split("_")[-1]
    name = c.from_user.first_name
    
    # Обновляем язык в воронке дожимов
    if c.from_user.id in active_tasks:
        active_tasks[c.from_user.id].cancel()
    active_tasks[c.from_user.id] = asyncio.create_task(marketing_funnel(c.from_user.id, name, lang))

    await c.message.edit_text(text=TEXTS[lang]["welcome"].format(name=name), reply_markup=main_kb(lang))
    await c.answer()

@dp.callback_query(F.data == "buy_stars")
async def process_buy_stars(c: CallbackQuery):
    user_id = c.from_user.id
    lang = get_user_lang(c)
    price = get_price(lang)

    # Лог админу о клике на кнопку покупки
    if ADMIN_ID and user_id != ADMIN_ID:
        try:
            username = f"@{c.from_user.username}" if c.from_user.username else "No User"
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🔥 <b>Клик по кнопке 'Купить':</b>\nID: <code>{user_id}</code>\nUser: {username}"
            )
        except Exception:
            pass

    await bot.send_invoice(
        chat_id=user_id,
        title=TEXTS[lang]["title"],
        description=TEXTS[lang]["desc"],
        payload=f"stars_{user_id}_{lang}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=price)],
        start_parameter="join_private"
    )
    await c.answer()

# =====================================================
# PAYMENTS PROCESSING
# =====================================================
@dp.pre_checkout_query()
async def process_pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(m: Message):
    user_id = m.from_user.id
    payload = m.successful_payment.invoice_payload
    
    # Извлекаем язык из payload инвойса
    try:
        lang = payload.split("_")[-1]
    except Exception:
        lang = "en"

    # Гасим фоновые дожимы
    if user_id in active_tasks:
        active_tasks[user_id].cancel()
        active_tasks.pop(user_id, None)

    # Обновляем статус в Supabase
    asyncio.create_task(update_payment_status(user_id))

    # Уведомление админа
    if ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"💰 <b>Успешная оплата (Stars)!</b>\nID: <code>{user_id}</code>\nСумма: {m.successful_payment.total_amount} XTR"
            )
        except Exception:
            pass

    await m.answer(text=f"{TEXTS[lang]['thanks']}\n\n{PRIVATE_LINK}")

# =====================================================
# LIVECHAT BACK-AND-FORTH (ADMIN INTERACTION)
# =====================================================
@dp.message(F.text & ~F.text.startswith("/"))
async def forward_to_admin(m: Message):
    if m.from_user.id == ADMIN_ID:
        return
    if ADMIN_ID:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✉️ <b>Сообщение от пользователя</b> <code>{m.from_user.id}</code>:\n\n{m.text}"
        )

@dp.message(F.reply_to_message & (F.chat.id == ADMIN_ID))
async def reply_from_admin(m: Message):
    match = re.search(r"(\d{6,15})", m.reply_to_message.text or "")
    if match:
        user_id = int(match.group(1))
        try:
            await bot.send_message(chat_id=user_id, text=m.text)
            await m.reply("✅ Отправлено")
        except Exception as e:
            await m.reply(f"❌ Не отправлено: {e}")

# =====================================================
# WEB SERVER & INITIALIZATION
# =====================================================
async def handle_ping(request):
    return web.Response(text="OK")

async def main():
    # Запуск веб-сервера для UptimeRobot на Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    logging.info(f"Keep-alive server runs on port {PORT}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
