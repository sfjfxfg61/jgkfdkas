import asyncio
import logging
import os
import re
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)

# =====================================================
# CONFIG
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))
PRIVATE_LINK = os.getenv("PRIVATE_CHANNEL_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()

# =====================================================
# MEMORY
# =====================================================

users = {}
tasks = {}
paid_users = set()  # Хранение оплативших юзеров (RAM)

# =====================================================
# GEO PRICING (мягкая психология цен)
# =====================================================

def get_price(lang: str) -> int:
    # Восточная Европа / СНГ
    if lang in ["uk", "ru"]:
        return 500

    # Западная Европа (более платежеспособные)
    if lang in ["en", "de"]:
        return 1000

    return 1000

# =====================================================
# WEB SERVER (Render keep alive)
# =====================================================

async def ok(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get("/", ok)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logging.info("Web server started")

# =====================================================
# TEXT FUNNEL (УЛУЧШЕННАЯ ПСИХОЛОГИЯ)
# =====================================================

TEXTS = {
    "uk": {
        "welcome": (
            "Привіт, {name} 🤍\n\n"
            "Я не зовсім випадково залишила це відкритим для тебе.\n\n"
            "Тут невеликий приватний простір — спокійний, без зайвого шуму, "
            "де я ділюся тим, що зазвичай не показую всім.\n\n"
            "Якщо тобі відгукується така атмосфера — ти можеш залишитися."
        ),
        "followup": (
            "{name}, ти ще тут? 🤍\n\n"
            "Я якраз додала нові матеріали в закритий простір.\n\n"
            "Зазвичай я не залишаю їх надовго відкритими — "
            "просто не люблю перевантажувати канал.\n\n"
            "Якщо ти хотів зайти — зараз хороший момент."
        ),
        "btn": "✨ Отримати доступ",
        "title": "Приватний простір",
        "desc": "Доступ до закритого каналу з особистим контентом",
        "thanks": (
            "Дякую тобі 🤍\n\n"
            "Твій доступ уже відкритий.\n\n"
            "Збережи спокійний вхід нижче:"
        ),
    },

    "en": {
        "welcome": (
            "Hey, {name} 🤍\n\n"
            "I didn’t leave this open by accident.\n\n"
            "This is a small private space — calm, quiet, without noise, "
            "where I share things I usually don’t post publicly.\n\n"
            "If this kind of atmosphere feels right to you, you’re welcome to stay."
        ),
        "followup": (
            "{name}, are you still here? 🤍\n\n"
            "I just added something new inside the private space.\n\n"
            "I usually don’t keep things open for too long — "
            "I like it to stay simple and intentional.\n\n"
            "If you were thinking about it… now is a good moment."
        ),
        "btn": "✨ Get access",
        "title": "Private space",
        "desc": "Exclusive access to private content",
        "thanks": (
            "Thank you 🤍\n\n"
            "Your access is now active.\n\n"
            "You can enter here:"
        ),
    },

    "ru": {
        "welcome": (
            "Привет, {name} 🤍\n\n"
            "Я не просто так оставила это открытым.\n\n"
            "Это небольшой закрытый уголок — спокойный, без лишнего шума, "
            "где я делюсь тем, что обычно не публикую.\n\n"
            "Если тебе откликается такая атмосфера — ты можешь остаться."
        ),
        "followup": (
            "{name}, ты ещё здесь? 🤍\n\n"
            "Я только что добавила новое внутри закрытого пространства.\n\n"
            "Обычно я не держу доступ открытым долго — "
            "мне важно, чтобы всё оставалось аккуратно и без перегруза.\n\n"
            "Если думал зайти — сейчас подходящий момент."
        ),
        "btn": "✨ Получить доступ",
        "title": "Закрытоеspace",
        "desc": "Доступ к приватному каналу",
        "thanks": (
            "Спасибо тебе 🤍\n\n"
            "Доступ уже открыт.\n\n"
            "Ссылка ниже:"
        ),
    },

    "de": {
        "welcome": (
            "Hey, {name} 🤍\n\n"
            "Ich habe das nicht zufällig offen gelassen.\n\n"
            "Das ist ein kleiner privater Raum — ruhig, ohne Ablenkung, "
            "wo ich Dinge teile, die ich normalerweise nicht öffentlich poste.\n\n"
            "Wenn sich das für dich richtig anfühlt, bist du willkommen."
        ),
        "followup": (
            "{name}, bist du noch da? 🤍\n\n"
            "Ich habe gerade neue Inhalte im privaten Bereich hinzugefügt.\n\n"
            "Ich lasse solche Zugänge normalerweise nicht lange offen — "
            "es soll bewusst und ruhig bleiben.\n\n"
            "Falls du überlegt hast reinzuschauen — jetzt ist ein guter Moment."
        ),
        "btn": "✨ Zugang erhalten",
        "title": "Privater Raum",
        "desc": "Exklusiver Zugang",
        "thanks": (
            "Danke dir 🤍\n\n"
            "Dein Zugang ist jetzt aktiv.\n\n"
            "Link unten:"
        ),
    },
}

# =====================================================
# KEYBOARD
# =====================================================

def lang_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇦 UA", callback_data="uk")],
            [InlineKeyboardButton(text="🇬🇧 EN", callback_data="en")],
            [InlineKeyboardButton(text="🇷🇺 RU", callback_data="ru")],
            [InlineKeyboardButton(text="🇩🇪 DE", callback_data="de")],
        ]
    )

def buy_kb(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["btn"], callback_data="buy")]
        ]
    )

# =====================================================
# FOLLOWUP FUNNEL (УЛУЧШЕННЫЙ + 2 ЭТАПА)
# =====================================================

async def followup(user_id: int):
    try:
        # 1-й этап: Ждем 10 минут (600 сек)
        await asyncio.sleep(600)

        if user_id in paid_users:
            return

        u = users.get(user_id)
        if not u:
            return

        lang = u["lang"]
        name = u["name"]

        # 1-й мягкий дожим
        await bot.send_message(
            user_id,
            TEXTS[lang]["followup"].format(name=name),
        )

        # 2-й этап: Ждем еще 5 минут (300 сек)
        await asyncio.sleep(300)

        if user_id in paid_users:
            return

        # 2-й дожим с инвойсом
        # Тексты дожима адаптированы под выбранную локаль
        remind_texts = {
            "uk": "Я не знаю, чи ти повернешся… 🤍\n\nАле доступ незабаром може закритися.",
            "en": "I don’t know if you’ll come back… 🤍\n\nBut access might close soon.",
            "ru": "Я не знаю, вернёшься ли ты… 🤍\n\nНо доступ скоро может закрыться.",
            "de": "Ich weiß nicht, ob du zurückkommst… 🤍\n\nAber der Zugang könnte bald schließen."
        }

        await bot.send_message(
            user_id,
            remind_texts.get(lang, remind_texts["en"])
        )

        price = get_price(lang)

        await bot.send_invoice(
            chat_id=user_id,
            title=TEXTS[lang]["title"],
            description=TEXTS[lang]["desc"],
            payload=f"pay_{user_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Access", amount=price)],
        )

    except Exception as e:
        logging.exception(e)

# =====================================================
# START + SOURCE TRACKING
# =====================================================

@dp.message(CommandStart())
async def start(m: Message):
    ref = m.text.split(" ")[1] if len(m.text.split()) > 1 else "direct"

    users[m.from_user.id] = {
        "name": m.from_user.first_name,
        "lang": None,
        "ref": ref,
    }

    await m.answer(
        "Choose language 🤍",
        reply_markup=lang_kb(),
    )

# =====================================================
# LANGUAGE SELECT
# =====================================================

@dp.callback_query(F.data.in_(["uk", "en", "ru", "de"]))
async def lang(c: CallbackQuery):
    u = users[c.from_user.id]
    u["lang"] = c.data

    # Защита от дублей тасок follow-up при повторном клике на флаг
    if c.from_user.id in tasks:
        tasks[c.from_user.id].cancel()

    tasks[c.from_user.id] = asyncio.create_task(followup(c.from_user.id))

    await c.message.answer(
        TEXTS[c.data]["welcome"].format(name=u["name"]),
        reply_markup=buy_kb(c.data),
    )

    await c.answer()

# =====================================================
# BUY HANDLER
# =====================================================

@dp.callback_query(F.data == "buy")
async def buy_handler(c: CallbackQuery):
    try:
        user_id = c.from_user.id

        # Блокировка повторных инвойсов, если оплачено
        if user_id in paid_users:
            already_paid_texts = {
                "uk": "У тебе вже є доступ 🤍",
                "en": "You already have access 🤍",
                "ru": "У тебя уже есть доступ 🤍",
                "de": "Du hast bereits Zugang 🤍"
            }
            u_lang = users.get(user_id, {}).get("lang", "en")
            await c.answer(already_paid_texts.get(u_lang, already_paid_texts["en"]))
            return

        u = users.get(user_id)
        if not u:
            await c.answer()
            return

        lang = u["lang"]

        step_texts = {
            "uk": "Ти майже всередині 🤍\n\nОстався один крок — підтвердження доступу.",
            "en": "You're almost inside 🤍\n\nOne last step — access confirmation.",
            "ru": "Ты почти внутри 🤍\n\nОстался один шаг — подтверждение доступа.",
            "de": "Du bist fast drin 🤍\n\nNur noch ein Schritt — Bestätigung des Zugangs."
        }

        await c.message.answer(step_texts.get(lang, step_texts["en"]))

        price = get_price(lang)

        await bot.send_invoice(
            chat_id=user_id,
            title=TEXTS[lang]["title"],
            description=TEXTS[lang]["desc"],
            payload=f"pay_{user_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Access", amount=price)],
        )

        await c.answer()

    except Exception as e:
        logging.exception(e)

# =====================================================
# PAYMENT
# =====================================================

@dp.pre_checkout_query()
async def pre(q: PreCheckoutQuery):
    await q.answer(True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def paid(m: Message):
    try:
        user_id = m.from_user.id
        lang = users[user_id]["lang"]

        # Добавляем в оплатившие и отменяем дожимы
        paid_users.add(user_id)
        if user_id in tasks:
            tasks[user_id].cancel()

        await m.answer(
            f"{TEXTS[lang]['thanks']}\n\n{PRIVATE_LINK}"
        )

    except Exception as e:
        logging.exception(e)

# =====================================================
# ADMIN FORWARD
# =====================================================

@dp.message(F.text)
async def to_admin(m: Message):
    if m.from_user.id == ADMIN_ID:
        return

    await bot.send_message(
        ADMIN_ID,
        f"ID:{m.from_user.id} | {m.text}",
    )

# =====================================================
# ADMIN REPLY
# =====================================================

@dp.message(F.reply_to_message)
async def reply(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    match = re.search(r"ID:(\d+)", m.reply_to_message.text or "")
    if not match:
        return

    uid = int(match.group(1))

    await bot.send_message(uid, m.text)

# =====================================================
# MAIN
# =====================================================

async def main():
    await start_web()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
