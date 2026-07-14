# handlers.py

import asyncio
import logging
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

import config
import database as db
from texts import TEXTS, get_user_lang, get_price
import keyboards

router = Router()
active_funnels = {}

async def run_delayed_trigger(bot: Bot, user_id: int, name: str, lang: str):
    """Трехэтапная воронка дожима с автопроверкой оплаты на каждом шаге"""
    try:
        # --- КАСАНИЕ 1: Открытие дверей (Через 2 минуты) ---
        await asyncio.sleep(120)
        
        user = await db.db_get_user(user_id)
        if not user or user.get("is_paid"):
            return

        await bot.send_message(
            chat_id=user_id,
            text=TEXTS[lang]["trigger"].format(name=name),
            reply_markup=keyboards.trigger_kb(lang)
        )

        # --- КАСАНИЕ 2: Социальное доказательство и FOMO (Через 30 минут) ---
        await asyncio.sleep(1800)
        
        user = await db.db_get_user(user_id)
        if not user or user.get("is_paid"):
            return

        proof_texts = {
            "ru": "🤍 <i>«Сначала я сомневался, но то, что внутри... это изменило всё. Без цензуры, без масок.»</i> — одно из десятков сообщений, которые я получаю.\n\nДоступ открыт еще совсем недолго. Не упускай возможность узнать меня настоящую.",
            "uk": "🤍 <i>«Спочатку я сумнівався, але те, що всередині... це змінило все. Без цензури, без масок.»</i> — одне з десятків повідомлень, які я отримую.\n\nДоступ відкритий ще зовсім трохи. Не упускай можливість дізнатися мене справжню.",
            "en": "🤍 <i>“At first I doubted, but what's inside... it changed everything. No filters, no masks.”</i> — one of the messages I receive daily.\n\nAccess is open for a limited time. Don't miss your chance."
        }
        text_proof = proof_texts.get(lang, proof_texts["en"])
        
        await bot.send_message(
            chat_id=user_id,
            text=text_proof,
            reply_markup=keyboards.trigger_kb(lang)
        )

        # --- КАСАНИЕ 3: Ультиматум и деактивация ссылки (Через 4 часа) ---
        await asyncio.sleep(14400)
        
        user = await db.db_get_user(user_id)
        if not user or user.get("is_paid"):
            return

        await bot.send_message(
            chat_id=user_id,
            text=TEXTS[lang]["push"],
            reply_markup=keyboards.trigger_kb(lang)
        )

    except asyncio.CancelledError:
        pass
    except TelegramForbiddenError:
        pass
    except Exception as e:
        logging.error(f"Error in automated funnel for {user_id}: {e}")
    finally:
        active_funnels.pop(user_id, None)

@router.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject):
    user_id = m.from_user.id
    ref = command.args if command.args else "direct"
    lang = get_user_lang(m.from_user.language_code)
    name = m.from_user.first_name
    username = f"@{m.from_user.username}" if m.from_user.username else "None"

    asyncio.create_task(db.db_upsert_user(user_id, username, name, lang, ref))
    pub_url = config.PUBLIC_CHANNELS.get(lang, config.PUBLIC_CHANNELS["en"])

    try:
        await m.answer(
            text=TEXTS[lang]["welcome"].format(name=name),
            reply_markup=keyboards.welcome_kb(lang, pub_url)
        )
    except TelegramForbiddenError:
        pass

@router.callback_query(F.data.startswith("check_sub_"))
async def process_check_sub(c: CallbackQuery, bot: Bot):
    lang = c.data.split("_")[-1]
    user_id = c.from_user.id
    name = c.from_user.first_name

    try:
        await c.answer("Аналіз профілю...", show_alert=False)
        await c.message.edit_text(text=TEXTS[lang]["checking"], reply_markup=None)
    except TelegramAPIError:
        pass

    if user_id in active_funnels:
        active_funnels[user_id].cancel()
    active_funnels[user_id] = asyncio.create_task(run_delayed_trigger(bot, user_id, name, lang))

@router.callback_query(F.data == "change_lang")
async def process_change_lang(c: CallbackQuery):
    try:
        await c.message.edit_text("Select language / Выберите язык:", reply_markup=keyboards.languages_kb())
        await c.answer()
    except TelegramAPIError:
        pass

@router.callback_query(F.data.startswith("set_lang_"))
async def process_set_lang(c: CallbackQuery):
    lang = c.data.split("_")[-1]
    name = c.from_user.first_name
    pub_url = config.PUBLIC_CHANNELS.get(lang, config.PUBLIC_CHANNELS["en"])
    try:
        await c.message.edit_text(text=TEXTS[lang]["welcome"].format(name=name), reply_markup=keyboards.welcome_kb(lang, pub_url))
        await c.answer()
    except TelegramAPIError:
        pass

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
                text=f"⚡️ <b>Клик по оплате:</b>\nID: <code>{user_id}</code>\nЮзер: {username}\nГео: {lang.upper()}"
            )
        except Exception:
            pass

    try:
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
    except TelegramForbiddenError:
        pass
    except Exception as e:
        logging.error(f"Invoice send error to {user_id}: {e}")

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

    if user_id in active_funnels:
        active_funnels[user_id].cancel()
        active_funnels.pop(user_id, None)

    asyncio.create_task(db.db_set_paid_status(user_id, True))

    if config.ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"💰 <b>ПРОДАЖА!</b>\nЮзер: <code>{user_id}</code>\nСумма: {m.successful_payment.total_amount} Stars"
            )
        except Exception:
            pass

    try:
        await m.answer(text=f"{TEXTS[lang]['thanks']}\n\n{config.PRIVATE_CHANNEL_URL}")
    except TelegramForbiddenError:
        pass

# ==================== АДМИН-ПАНЕЛЬ И КОМАНДЫ ====================

@router.message(Command("stats"), F.from_user.id == config.ADMIN_ID)
async def cmd_stats(m: Message):
    st = await db.db_get_stats()
    if not st:
        return await m.answer("Ошибка получения статистики.")
    
    ref_text = "\n".join([f" ├ <code>{k}</code>: {v} уников" for k, v in st['refs'].items()])
    text = (
        f"📊 <b>СТАТИСТИКА БОТА:</b>\n\n"
        f"👥 Всего пользователей: <b>{st['total']}</b>\n"
        f"💰 Оплатили приватку: <b>{st['paid']}</b>\n"
        f"📉 Конверсия в оплату: <b>{round((st['paid']/max(st['total'],1))*100, 1)}%</b>\n\n"
        f"🔗 <b>Реферальные хвосты:</b>\n{ref_text}"
    )
    await m.answer(text)

@router.message(Command("user"), F.from_user.id == config.ADMIN_ID)
async def cmd_user(m: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await m.answer("Формат: <code>/user 123456789</code>")
    uid = int(command.args)
    u = await db.db_get_user(uid)
    if not u:
        return await m.answer("Пользователь не найден в базе.")
    
    text = (
        f"👤 <b>Профиль юзера:</b>\n"
        f"ID: <code>{u['user_id']}</code>\n"
        f"Имя: {u['first_name']}\n"
        f"Телега: {u['username']}\n"
        f"Язык: <code>{u['lang']}</code>\n"
        f"Реф: <code>{u['ref']}</code>\n"
        f"Статус оплаты: <b>{'✅ Оплачено' if u['is_paid'] else '❌ Не оплачено'}</b>"
    )
    await m.answer(text, reply_markup=keyboards.admin_user_kb(uid, u['is_paid']))

@router.callback_query(F.data.startswith("adm_toggle_"), F.from_user.id == config.ADMIN_ID)
async def process_toggle_pay(c: CallbackQuery):
    _, action, uid = c.data.split("_")
    uid = int(uid)
    new_status = (action == "give")
    await db.db_set_paid_status(uid, new_status)
    try:
        await c.message.edit_text(f"Статус оплаты для <code>{uid}</code> изменен на: <b>{new_status}</b>")
        await c.answer("Статус обновлен")
    except TelegramAPIError:
        pass

@router.message(Command("broadcast"), F.from_user.id == config.ADMIN_ID)
async def cmd_broadcast(m: Message, command: CommandObject, bot: Bot):
    if not command.args:
        return await m.answer("Формат: <code>/broadcast Текст</code>")
    
    unpaid_users = await db.db_get_unpaid_users()
    await m.answer(f"🚀 Запускаю ручную рассылку на {len(unpaid_users)} пользователей...")
    
    count = 0
    for u in unpaid_users:
        try:
            await bot.send_message(chat_id=u["user_id"], text=command.args)
            count += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            pass
        except Exception:
            continue
    await m.answer(f"✅ Рассылка завершена. Доставлено: {count} писем.")

@router.message(Command("send"), F.from_user.id == config.ADMIN_ID)
async def cmd_send_direct(m: Message, command: CommandObject, bot: Bot):
    """Формат: /send 123456789 Твой текст сообщения любого объема"""
    if not command.args:
        return await m.answer("Использование: <code>/send [ID] [Текст сообщения]</code>")
    
    parts = command.args.split(" ", 1)
    if len(parts) < 2 or not parts[0].isdigit():
        return await m.answer("Ошибка формата. Пример: <code>/send 123456789 Твой текст</code>")
    
    target_id = int(parts[0])
    text_to_send = parts[1]
    
    try:
        await bot.send_message(chat_id=target_id, text=text_to_send)
        await m.reply(f"✅ Доставлено пользователю <code>{target_id}</code>")
    except TelegramForbiddenError:
        await m.reply(f"❌ Юзер <code>{target_id}</code> заблокировал бота.")
    except Exception as e:
        await m.reply(f"❌ Ошибка отправки: {e}")

@router.message(Command("cleanup"), F.from_user.id == config.ADMIN_ID)
async def cmd_cleanup_database(m: Message, bot: Bot):
    """Очищает базу данных от тех, кто заблокировал бота"""
    await m.answer("🧹 Начинаю чистку базы от заблокировавших бота... Это может занять время.")
    unpaid_users = await db.db_get_unpaid_users()
    
    removed_count = 0
    checked_count = 0
    
    for u in unpaid_users:
        uid = u["user_id"]
        checked_count += 1
        try:
            await bot.send_chat_action(chat_id=uid, action="typing")
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            await db.db_delete_user(uid)
            removed_count += 1
        except Exception:
            pass
            
    await m.answer(
        f"✅ <b>Очистка завершена!</b>\n"
        f"🔍 Проверено: <b>{checked_count}</b>\n"
        f"🗑 Удалено из базы: <b>{removed_count}</b>"
    )

# ==================== ЛАЙВ-ЧАТ ====================

@router.message(F.text & ~F.text.startswith("/"))
async def forward_to_admin(m: Message, bot: Bot):
    if m.from_user.id == config.ADMIN_ID:
        return
    try:
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=f"✉️ <b>TICKET_ID:</b> <code>{m.from_user.id}</code>\n"
                 f"👤 От: {m.from_user.first_name}\n\n"
                 f"{m.text}"
        )
    except Exception as e:
        logging.error(f"Failed to forward message to admin: {e}")

@router.message(F.reply_to_message & (F.chat.id == config.ADMIN_ID))
async def reply_from_admin(m: Message, bot: Bot):
    reply_text = m.reply_to_message.text or ""
    if "TICKET_ID:" not in reply_text:
        return
    
    try:
        first_line = reply_text.split("\n")[0]
        user_id = int(first_line.replace("✉️ TICKET_ID:", "").replace("<b>", "").replace("</b>", "").strip())
        
        await bot.send_message(chat_id=user_id, text=m.text)
        await m.reply(f"🚀 <b>Ответ отправлен юзеру</b> (<code>{user_id}</code>)")
    except TelegramForbiddenError:
        await m.reply(f"❌ Ошибка: Юзер <code>{user_id}</code> заблокировал бота.")
    except Exception as e:
        await m.reply(f"❌ Ошибка: {e}")
