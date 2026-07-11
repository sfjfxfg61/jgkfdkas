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
active_funnels = {}  # Карта запущенных тасков дожима в оперативной памяти

async def run_delayed_trigger(bot: Bot, user_id: int, name: str, lang: str):
    """Фоновый таймер дожима: триггер срабатывает через 120 секунд после клика 'Я подписался'"""
    try:
        await asyncio.sleep(120)  # Психологическое время удержания — 2 минуты
        
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
async def cmd_start(m: Message, command: CommandObject):
    user_id = m.from_user.id
    ref = command.args if command.args else "direct"
    lang = get_user_lang(m.from_user.language_code)
    name = m.from_user.first_name
    username = f"@{m.from_user.username}" if m.from_user.username else "None"

    # Асинхронное сохранение в Supabase
    asyncio.create_task(db_upsert_user(user_id, username, name, lang, ref))
    pub_url = config.PUBLIC_CHANNELS.get(lang, config.PUBLIC_CHANNELS["en"])

    await m.answer(
        text=TEXTS[lang]["welcome"].format(name=name),
        reply_markup=keyboards.welcome_kb(lang, pub_url)
    )

@router.callback_query(F.data.startswith("check_sub_"))
async def process_check_sub(c: CallbackQuery, bot: Bot):
    lang = c.data.split("_")[-1]
    user_id = c.from_user.id
    name = c.from_user.first_name

    # Анимация уведомления в самом Telegram (фидбек клика)
    await c.answer("Анкета обрабатывается...", show_alert=False)

    # Имитируем «проверку профиля», переключая интерфейс
    await c.message.edit_text(
        text=TEXTS[lang]["checking"],
        reply_markup=None  # Убираем кнопки, фиксируя внимание на тексте ожидания
    )

    # Запускаем фоновый дожим на 2 минуты
    if user_id in active_funnels:
        active_funnels[user_id].cancel()
    active_funnels[user_id] = asyncio.create_task(run_delayed_trigger(bot, user_id, name, lang))

@router.callback_query(F.data == "change_lang")
async def process_change_lang(c: CallbackQuery):
    await c.message.edit_text("Select language / Выберите язык:", reply_markup=keyboards.languages_kb())
    await c.answer()

@router.callback_query(F.data.startswith("set_lang_"))
async def process_set_lang(c: CallbackQuery):
    lang = c.data.split("_")[-1]
    name = c.from_user.first_name
    pub_url = config.PUBLIC_CHANNELS.get(lang, config.PUBLIC_CHANNELS["en"])

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

    if config.ADMIN_ID and user_id != config.ADMIN_ID:
        try:
            username = f"@{c.from_user.username}" if c.from_user.username else "No User"
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"🔥 <b>Клик по инвойсу (Stars):</b>\nID: <code>{user_id}</code>\nЮзер: {username}\nГео: {lang.upper()}"
            )
        except Exception:
            pass

    await bot.send_invoice(
        chat_id=user_id,
        title=TEXTS[lang]["invoice_title"],
        description=TEXTS[lang]["invoice_desc"],
        payload=f"stars_{user_id}_{lang}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Telegram Stars", amount=price)],
        start_parameter="pay_private"
    )
    await c.answer()

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

    # Гасим фоновый таймер дожима, так как человек купил
    if user_id in active_funnels:
        active_funnels[user_id].cancel()
        active_funnels.pop(user_id, None)

    # Асинхронно обновляем статус оплаты в Supabase
    asyncio.create_task(db_set_paid_status(user_id))

    if config.ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"💰 <b>УСПЕШНАЯ ОПЛАТА!</b>\nЮзер: <code>{user_id}</code>\nСумма: {m.successful_payment.total_amount} XTR"
            )
        except Exception:
            pass

    await m.answer(text=f"{TEXTS[lang]['thanks']}\n\n{config.PRIVATE_CHANNEL_URL}")

# ЛАЙВ-ЧАТ ДЛЯ СВЯЗИ С АДМИНИСТРАТОРОМ
@router.message(F.text & ~F.text.startswith("/"))
async def forward_to_admin(m: Message, bot: Bot):
    if m.from_user.id == config.ADMIN_ID or not config.ADMIN_ID:
        return
    await bot.send_message(
        chat_id=config.ADMIN_ID,
        text=f"✉️ <b>Сообщение от</b> <code>{m.from_user.id}</code>:\n\n{m.text}"
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
            await m.reply(f"❌ Ошибка отправки: {e}")
