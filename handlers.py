import asyncio
import logging
import re
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery

import config
from database import db_upsert_user, db_set_paid_status
from texts import TEXTS, get_user_lang, get_price
import keyboards

router = Router()
active_funnels = {}  # RAM-карта активных тасков дожима для отмены при покупке

async def run_delayed_trigger(bot: Bot, user_id: int, name: str, lang: str):
    """Маркетинговый дожим: срабатывает строго через 5 минут после старта"""
    try:
        await asyncio.sleep(300)  # 5 минут (300 секунд)
        
        await bot.send_message(
            chat_id=user_id,
            text=TEXTS[lang]["trigger"].format(name=name),
            reply_markup=keyboards.trigger_kb(lang)
        )
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Error in funnel for user {user_id}: {e}")
    finally:
        active_funnels.pop(user_id, None)

@router.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject, bot: Bot):
    user_id = m.from_user.id
    ref = command.args if command.args else "direct"
    lang = get_user_lang(m.from_user.language_code)
    name = m.from_user.first_name
    username = f"@{m.from_user.username}" if m.from_user.username else "None"

    # Шаг 1: Асинхронно сохраняем в БД, не нагружая поток
    asyncio.create_task(db_upsert_user(user_id, username, name, lang, ref))

    # Шаг 2: Получаем ссылку на открытый канал под язык
    pub_url = config.PUBLIC_CHANNELS.get(lang, config.PUBLIC_CHANNELS["en"])

    # Шаг 3: Сбрасываем старый таймер воронки, если он был, и запускаем новый
    if user_id in active_funnels:
        active_funnels[user_id].cancel()
    active_funnels[user_id] = asyncio.create_task(run_delayed_trigger(bot, user_id, name, lang))

    await m.answer(
        text=TEXTS[lang]["welcome"].format(name=name),
        reply_markup=keyboards.welcome_kb(lang, pub_url)
    )

@router.callback_query(F.data == "change_lang")
async def process_change_lang(c: CallbackQuery):
    await c.message.edit_text("Select language / Выберите язык:", reply_markup=keyboards.languages_kb())
    await c.answer()

@router.callback_query(F.data.startswith("set_lang_"))
async def process_set_lang(c: CallbackQuery, bot: Bot):
    lang = c.data.split("_")[-1]
    user_id = c.from_user.id
    name = c.from_user.first_name
    pub_url = config.PUBLIC_CHANNELS.get(lang, config.PUBLIC_CHANNELS["en"])

    if user_id in active_funnels:
        active_funnels[user_id].cancel()
    active_funnels[user_id] = asyncio.create_task(run_delayed_trigger(bot, user_id, name, lang))

    await c.message.edit_text(
        text=TEXTS[lang]["welcome"].format(name=name),
        reply_markup=keyboards.welcome_kb(lang, pub_url)
    )
    await c.answer()

@router.callback_query(F.data.startswith("buy_trigger_"))
async def process_buy(c: CallbackQuery, bot: Bot):
    user_id = c.from_user.id
    lang = c.data.split("_")[-1]
    price = get_price(lang)

    # Админ-нотификация о проявленном интересе
    if config.ADMIN_ID and user_id != config.ADMIN_ID:
        try:
            username = f"@{c.from_user.username}" if c.from_user.username else "No User"
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"🔥 <b>Юзер открыл инвойс:</b>\nID: <code>{user_id}</code>\nUser: {username}\nGeo: {lang.upper()}"
            )
        except Exception:
            pass

    await bot.send_invoice(
        chat_id=user_id,
        title=TEXTS[lang]["invoice_title"],
        description=TEXTS[lang]["invoice_desc"],
        payload=f"stars_{user_id}_{lang}",
        provider_token="",  # Для Stars всегда пусто
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=price)],
        start_parameter="pay_private"
    )
    await c.answer()

# =====================================================
# ОБРАБОТКА ТРАНЗАКЦИЙ (TELEGRAM STARS)
# =====================================================
@router.pre_checkout_query()
async def process_pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(m: Message, bot: Bot):
    user_id = m.from_user.id
    payload = m.successful_payment.invoice_payload
    
    try:
        lang = payload.split("_")[-1]
    except Exception:
        lang = "en"

    # Удаляем фоновые дожимы, так как покупка совершена
    if user_id in active_funnels:
        active_funnels[user_id].cancel()
        active_funnels.pop(user_id, None)

    # Запись в БД об оплате
    asyncio.create_task(db_set_paid_status(user_id))

    if config.ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"💰 <b>ПРОДАЖА!</b>\nЮзер: <code>{user_id}</code>\nПолучено: {m.successful_payment.total_amount} XTR"
            )
        except Exception:
            pass

    await m.answer(text=f"{TEXTS[lang]['thanks']}\n\n{config.PRIVATE_CHANNEL_URL}")

# =====================================================
# ЛАЙВ-ЧАТ С АДМИНОМ (ДЛЯ РУЧНОГО ДОЖИМА)
# =====================================================
@router.message(F.text & ~F.text.startswith("/"))
async def forward_to_admin(m: Message, bot: Bot):
    if m.from_user.id == config.ADMIN_ID or not config.ADMIN_ID:
        return
    await bot.send_message(
        chat_id=config.ADMIN_ID,
        text=f"✉️ <b>Чат с юзером</b> <code>{m.from_user.id}</code>:\n\n{m.text}"
    )

@router.message(F.reply_to_message & (F.chat.id == config.ADMIN_ID))
async def reply_from_admin(m: Message, bot: Bot):
    match = re.search(r"(\d{6,15})", m.reply_to_message.text or "")
    if match:
        user_id = int(match.group(1))
        try:
            await bot.send_message(chat_id=user_id, text=m.text)
            await m.reply("✅ Отправлено")
        except Exception as e:
            await m.reply(f"❌ Сбой отправки: {e}")
