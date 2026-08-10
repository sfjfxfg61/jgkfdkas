# handlers.py

import asyncio
import logging
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

import config
import database as db
from texts import TEXTS, get_user_lang, get_tariff_price, get_text
import keyboards
from ai_closer import generate_ai_push

router = Router()

# Хранилище активных задач дожима
active_funnels = {}

async def run_delayed_trigger(bot: Bot, user_id: int, name: str, lang: str):
    """
    Высококонверсионная цепочка дожимов с генерацией ИИ-сообщений.
    """
    try:
        # --- КАСАНИЕ 1 (Через 30 секунд после подписки) ---
        await asyncio.sleep(30)
        
        user = await db.db_get_user(user_id)
        if not user or user.get("is_paid"):
            return

        await bot.send_message(
            chat_id=user_id,
            text=get_text(lang, "trigger").format(name=name),
            reply_markup=keyboards.trigger_kb(lang),
            parse_mode="HTML"
        )

        # --- КАСАНИЕ 2 (Через 30 минут) — Социальное доказательство ---
        await asyncio.sleep(1800)
        
        user = await db.db_get_user(user_id)
        if not user or user.get("is_paid"):
            return

        proof_texts = {
            "ru": "🤍 <i>«Сначала сомневался, но безлимит за 400 звезд — лучшее решение. Внутри реально контент без рамок.»</i> — пишут мне в чат.\n\nОсталось совсем немного времени до закрытия дверей. Выбери свой уровень доступа 👇",
            "uk": "🤍 <i>«Спочатку сумнівався, але безліміт за 400 зірок — найкраще рішення. Всередині реально контент без рамок.»</i> — пишуть мені в чат.\n\nВхід незабаром закриється. Обери свій рівень доступу 👇",
            "en": "🤍 <i>“Thought about it for a while, but lifetime access is a steal. No regrets, the content is insane.”</i> — feedback from the chat.\n\nDoors are closing soon. Choose your level below 👇",
            "es": "🤍 <i>“Al principio dudaba, pero el acceso ilimitado es la mejor decisión. El contenido de dentro es una locura.”</i> — comentarios de los usuarios.\n\nEl acceso se cerrará pronto. Elige tu plan abajo 👇",
            "fr": "🤍 <i>« Au début j'hésitais, mais l'accès à vie est incroyable. Le contenu est juste fou. »</i> — retours des membres.\n\nL'accès ferme bientôt. Choisis ton forfait ci-dessous 👇",
            "de": "🤍 <i>„Zuerst war ich skeptisch, aber der lebenslange Zugang ist die beste Entscheidung. Der Inhalt ist der Wahnsinn.“</i> — Feedback aus dem Chat.\n\nDer Zugang schließt bald. Wähle dein Paket unten 👇"
        }
        text_proof = proof_texts.get(lang, proof_texts["en"])
        
        await bot.send_message(
            chat_id=user_id,
            text=text_proof,
            reply_markup=keyboards.trigger_kb(lang),
            parse_mode="HTML"
        )

        # --- КАСАНИЕ 3 (Через 4 часа) — Динамический ИИ-дожим ---
        await asyncio.sleep(14400)
        
        user = await db.db_get_user(user_id)
        if not user or user.get("is_paid"):
            return

        prompt = (
            "Пользователь зашел в бота, просмотрел тарифы закрытого канала, но так и не купил подписку. "
            "Напиши ему 1 короткую интригующую фразу от своего лица, напомнив, "
            "что персональное приглашение скоро сгорит."
        )
        ai_push_text = await generate_ai_push(user_message=prompt, lang=lang)

        # Фоллбек на статический текст из texts.py, если API недоступно
        if not ai_push_text:
            ai_push_text = get_text(lang, "push")

        await bot.send_message(
            chat_id=user_id,
            text=ai_push_text,
            reply_markup=keyboards.trigger_kb(lang),
            parse_mode="HTML"
        )

    except asyncio.CancelledError:
        pass
    except TelegramForbiddenError:
        pass
    except Exception as e:
        logging.error(f"Error in delayed funnel for {user_id}: {e}")
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
            text=get_text(lang, "welcome").format(name=name),
            reply_markup=keyboards.welcome_kb(lang, pub_url),
            parse_mode="HTML"
        )
    except TelegramForbiddenError:
        pass


@router.callback_query(F.data.startswith("chk_"))
async def process_check_subscription(c: CallbackQuery, bot: Bot):
    """Нажатие на кнопку проверки подписки"""
    lang = c.data.split("_")[-1]
    user_id = c.from_user.id
    name = c.from_user.first_name

    try:
        await c.answer()
        await c.message.edit_text(text=get_text(lang, "checking"), reply_markup=None, parse_mode="HTML")
    except TelegramAPIError:
        pass

    if user_id in active_funnels:
        active_funnels[user_id].cancel()
    
    active_funnels[user_id] = asyncio.create_task(run_delayed_trigger(bot, user_id, name, lang))


@router.callback_query(F.data == "lng_change")
async def process_language_change(c: CallbackQuery):
    """Смена языка интерфейса"""
    try:
        await c.message.edit_text("Select language / Выберите язык:", reply_markup=keyboards.languages_kb())
        await c.answer()
    except TelegramAPIError:
        pass


@router.callback_query(F.data.startswith("lng_set_"))
async def process_language_save(c: CallbackQuery):
    """Сохранение выбранного языка"""
    lang = c.data.split("_")[-1]
    name = c.from_user.first_name
    pub_url = config.PUBLIC_CHANNELS.get(lang, config.PUBLIC_CHANNELS["en"])
    
    asyncio.create_task(db.db_upsert_user(
        c.from_user.id, 
        f"@{c.from_user.username}" if c.from_user.username else "None", 
        name, 
        lang, 
        "direct"
    ))

    try:
        await c.message.edit_text(
            text=get_text(lang, "welcome").format(name=name), 
            reply_markup=keyboards.welcome_kb(lang, pub_url),
            parse_mode="HTML"
        )
        await c.answer()
    except TelegramAPIError:
        pass


@router.callback_query(F.data.startswith("pay_"))
async def process_payment_generation(c: CallbackQuery, bot: Bot):
    """Генерация счета на оплату через Telegram Stars"""
    user_id = c.from_user.id
    _, tier, lang = c.data.split("_")
    
    price = get_tariff_price(lang, tier)
    tier_label = get_text(lang, f"tier_{tier}")

    if config.ADMIN_ID and user_id != config.ADMIN_ID:
        try:
            username = f"@{c.from_user.username}" if c.from_user.username else "NoUsername"
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"⚡️ <b>Клик по кнопке оплаты:</b>\nID: <code>{user_id}</code>\nЮзер: {username}\nТариф: {tier_label} ({price} ★)",
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=get_text(lang, "invoice_title").format(tier_name=tier_label),
            description=get_text(lang, "invoice_desc"),
            payload=f"stars_{user_id}_{tier}_{lang}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Telegram Stars", amount=price)],
            start_parameter="pay_private"
        )
        await c.answer()
    except TelegramForbiddenError:
        pass
    except Exception as e:
        logging.error(f"Error sending invoice to {user_id}: {e}")


@router.pre_checkout_query()
async def process_pre_checkout(q: PreCheckoutQuery):
    """Подтверждение платежа"""
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(m: Message, bot: Bot):
    """Обработка успешного платежа"""
    user_id = m.from_user.id
    payload = m.successful_payment.invoice_payload
    
    try:
        parts = payload.split("_")
        tier = parts[2]
        lang = parts[3]
    except Exception:
        tier = "lifetime"
        lang = "en"

    if user_id in active_funnels:
        active_funnels[user_id].cancel()
        active_funnels.pop(user_id, None)

    asyncio.create_task(db.db_set_paid_status(user_id, True))

    if config.ADMIN_ID:
        try:
            tier_label = get_text(lang, f"tier_{tier}")
            await bot.send_message(
                chat_id=config.ADMIN_ID,
                text=f"💰 <b>НОВАЯ ОПЛАТА!</b>\nЮзер: <code>{user_id}</code>\nТариф: {tier_label}\nСумма: {m.successful_payment.total_amount} Stars",
                parse_mode="HTML"
            )
        except Exception:
            pass

    try:
        await m.answer(text=f"{get_text(lang, 'thanks')}\n\n{config.PRIVATE_CHANNEL_URL}")
    except TelegramForbiddenError:
        pass


# ==================== АДМИНИСТРАТИВНАЯ ЧАСТЬ ====================

@router.message(Command("stats"), F.from_user.id == config.ADMIN_ID)
async def cmd_stats(m: Message):
    st = await db.db_get_stats()
    if not st:
        return await m.answer("Ошибка доступа к статистике.")
    
    ref_text = "\n".join([f" ├ <code>{k}</code>: {v} уников" for k, v in st['refs'].items()])
    text = (
        f"📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА:</b>\n\n"
        f"👥 Всего пользователей: <b>{st['total']}</b>\n"
        f"💰 Оплат приватного канала: <b>{st['paid']}</b>\n"
        f"📉 Общая конверсия: <b>{round((st['paid']/max(st['total'],1))*100, 1)}%</b>\n\n"
        f"🔗 <b>Переходы по источникам (TikTok):</b>\n{ref_text}"
    )
    await m.answer(text, parse_mode="HTML")


@router.message(Command("user"), F.from_user.id == config.ADMIN_ID)
async def cmd_user(m: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await m.answer("Пример: <code>/user 123456789</code>", parse_mode="HTML")
    
    uid = int(command.args)
    u = await db.db_get_user(uid)
    if not u:
        return await m.answer("Пользователь не найден.")
    
    text = (
        f"👤 <b>Карточка пользователя:</b>\n"
        f"ID: <code>{u['user_id']}</code>\n"
        f"Имя: {u['first_name']}\n"
        f"Телега: {u['username']}\n"
        f"Язык: <code>{u['lang']}</code>\n"
        f"Источник: <code>{u['ref']}</code>\n"
        f"Подписка: <b>{'✅ Активна' if u['is_paid'] else '❌ Отсутствует'}</b>"
    )
    await m.answer(text, reply_markup=keyboards.admin_user_kb(uid, u['is_paid']), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_tgl_"), F.from_user.id == config.ADMIN_ID)
async def process_toggle_access(c: CallbackQuery):
    _, action, uid = c.data.split("_")
    uid = int(uid)
    new_status = (action == "give")
    
    await db.db_set_paid_status(uid, new_status)
    try:
        await c.message.edit_text(f"Доступ для <code>{uid}</code> изменен на: <b>{new_status}</b>", parse_mode="HTML")
        await c.answer("Статус обновлен!")
    except TelegramAPIError:
        pass


@router.message(Command("broadcast"), F.from_user.id == config.ADMIN_ID)
async def cmd_broadcast(m: Message, command: CommandObject, bot: Bot):
    if not command.args:
        return await m.answer("Пример: <code>/broadcast Текст для рассылки</code>", parse_mode="HTML")
    
    unpaid_users = await db.db_get_unpaid_users()
    await m.answer(f"🚀 Запускаю рассылку на {len(unpaid_users)} получателей...")
    
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
    await m.answer(f"✅ Рассылка завершена. Успешно доставлено: {count} писем.")


@router.message(Command("send"), F.from_user.id == config.ADMIN_ID)
async def cmd_send_direct(m: Message, command: CommandObject, bot: Bot):
    if not command.args:
        return await m.answer("Пример: <code>/send 123456789 Привет</code>", parse_mode="HTML")
    
    parts = command.args.split(" ", 1)
    if len(parts) < 2 or not parts[0].isdigit():
        return await m.answer("Неверный формат. Пример: <code>/send 123456789 Привет</code>", parse_mode="HTML")
    
    target_id = int(parts[0])
    text_to_send = parts[1]
    
    try:
        await bot.send_message(chat_id=target_id, text=text_to_send)
        await m.reply(f"✅ Сообщение доставлено пользователю <code>{target_id}</code>", parse_mode="HTML")
    except TelegramForbiddenError:
        await m.reply("❌ Юзер заблокировал бота.")
    except Exception as e:
        await m.reply(f"❌ Ошибка: {e}")


@router.message(Command("cleanup"), F.from_user.id == config.ADMIN_ID)
async def cmd_cleanup(m: Message, bot: Bot):
    await m.answer("🧹 Сканирую базу на предмет блокировок...")
    unpaid = await db.db_get_unpaid_users()
    
    removed = 0
    checked = 0
    for u in unpaid:
        uid = u["user_id"]
        checked += 1
        try:
            await bot.send_chat_action(chat_id=uid, action="typing")
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            await db.db_delete_user(uid)
            removed += 1
        except Exception:
            pass
            
    await m.answer(
        f"✅ <b>Чистка завершена!</b>\n"
        f"🔍 Проверено аккаунтов: <b>{checked}</b>\n"
        f"🗑 Удалено 'мертвых душ': <b>{removed}</b>",
        parse_mode="HTML"
    )


# ==================== УМНЫЙ ИИ-ОТВЕТЧИК И ЛАЙВ-ЧАТ ====================

@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_text(m: Message, bot: Bot):
    """
    Обработка входящих сообщений: ИИ отвечает пользователю в реальном времени + копирует диалог в админку.
    """
    if m.from_user.id == config.ADMIN_ID:
        return

    user_id = m.from_user.id
    lang = get_user_lang(m.from_user.language_code)

    # 1. Пересылаем вопрос админу для тикет-системы
    try:
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=f"✉️ <b>TICKET_ID:</b> <code>{user_id}</code>\n"
                 f"👤 От: {m.from_user.first_name}\n\n"
                 f"{m.text}",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить тикет админу: {e}")

    # 2. Показываем индикатор набора текста
    try:
        await bot.send_chat_action(chat_id=user_id, action="typing")
    except Exception:
        pass

    # 3. Генерируем ответ через ИИ
    ai_reply = await generate_ai_push(user_message=m.text, lang=lang)

    # 4. Отправляем ответ ИИ с кнопками выбора тарифа
    try:
        if ai_reply:
            await m.answer(text=ai_reply, reply_markup=keyboards.trigger_kb(lang))
        else:
            await m.answer(text=get_text(lang, "trigger"), reply_markup=keyboards.trigger_kb(lang), parse_mode="HTML")
    except TelegramForbiddenError:
        pass


@router.message(F.reply_to_message & (F.chat.id == config.ADMIN_ID))
async def reply_from_admin(m: Message, bot: Bot):
    """Ответ админа из группы/чата отправляется обратно пользователю"""
    reply_text = m.reply_to_message.text or ""
    if "TICKET_ID:" not in reply_text:
        return
    
    try:
        first_line = reply_text.split("\n")[0]
        user_id = int(first_line.replace("✉️ TICKET_ID:", "").replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").strip())
        
        await bot.send_message(chat_id=user_id, text=m.text)
        await m.reply(f"🚀 <b>Ответ отправлен юзеру</b> (<code>{user_id}</code>)", parse_mode="HTML")
    except TelegramForbiddenError:
        await m.reply("❌ Не удалось отправить. Юзер заблокировал бота.")
    except Exception as e:
        await m.reply(f"❌ Ошибка отправки: {e}")
