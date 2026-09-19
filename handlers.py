from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

import keyboards
from ai_companion import companion_ai
from config import settings
from database import DatabaseError, store
from domain import compact_text, normalize_lang, premium_is_active, relationship_level
from monetization import (
    PRODUCTS,
    SUBSCRIPTION_PERIOD,
    default_market,
    entitlements,
    make_payload,
    parse_payload,
    paywall_text,
    price,
)
from texts import t

router = Router()
logger = logging.getLogger(__name__)
_user_locks: dict[int, asyncio.Lock] = {}


def _lock(user_id: int) -> asyncio.Lock:
    return _user_locks.setdefault(user_id, asyncio.Lock())


def _tier(user: dict | None) -> str:
    if not user or not premium_is_active(user):
        return "free"
    return user.get("subscription_tier") or "plus"


def _takeover_active(user: dict | None) -> bool:
    raw = (user or {}).get("human_takeover_until")
    if not raw:
        return False
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except ValueError:
        return False


def _is_hot_lead(text: str) -> bool:
    normalized = text.casefold()
    terms = {
        "price", "cost", "buy", "pay", "payment", "plan", "premium", "subscribe", "expensive", "human", "manager",
        "цена", "сколько", "купить", "оплат", "тариф", "премиум", "подпис", "дорого", "человек", "менеджер",
        "ціна", "скільки", "купити", "оплат", "підпис", "тариф", "дорого", "людина", "менеджер",
        "precio", "comprar", "pagar", "pago", "plan", "suscrip", "caro", "persona",
        "prix", "acheter", "payer", "paiement", "offre", "abonn", "cher", "humain",
        "preis", "kaufen", "zahlen", "zahlung", "abo", "teuer", "mensch",
    }
    return any(term in normalized for term in terms)


def _format_breakdown(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "—"
    return ", ".join(
        f"{html.escape(str(key))}: <b>{html.escape(str(amount))}</b>"
        for key, amount in value.items()
    )


async def _notify_admin(message: Message, bot: Bot, user: dict, user_text: str) -> None:
    if not settings.admin_id or message.from_user.id == settings.admin_id:
        return
    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    ticket = (
        f"<b>TICKET_ID:</b> <code>{message.from_user.id}</code>\n"
        f"From: {html.escape(message.from_user.first_name or 'User')} · {html.escape(username)}\n"
        f"Lang: <code>{html.escape(str(user.get('lang', 'en')))}</code> · "
        f"Tier: <code>{html.escape(_tier(user))}</code>\n\n"
        f"{html.escape(user_text)}"
    )
    try:
        await bot.send_message(settings.admin_id, ticket)
    except Exception:
        logger.warning("Could not deliver ticket for user %s", message.from_user.id)


async def _edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if not callback.message:
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


async def _user(callback: CallbackQuery) -> tuple[dict | None, str]:
    user = await store.get_user(callback.from_user.id)
    lang = (user or {}).get("lang") or normalize_lang(callback.from_user.language_code)
    return user, lang


@router.message(CommandStart())
async def start(message: Message, command: CommandObject) -> None:
    lang = normalize_lang(message.from_user.language_code)
    ref = compact_text(command.args or "direct", 80)
    market = default_market(lang, ref)
    user = await store.upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name or "User",
        lang,
        ref,
        market,
    )
    await store.track_event(message.from_user.id, "start", {"ref": ref, "lang": lang, "market": user.get("market")})
    if not user.get("onboarding_complete") or user.get("style") != "playful":
        user = await store.update_user(message.from_user.id, onboarding_complete=True, style="playful")
        await store.track_event(message.from_user.id, "onboarding_completed", {"style": "playful"})
    safe_name = html.escape(message.from_user.first_name or "")
    await message.answer(t(lang, "welcome", name=safe_name), reply_markup=keyboards.main_kb(lang))


@router.message(Command("menu"))
async def menu_command(message: Message) -> None:
    user = await store.get_user(message.from_user.id)
    lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
    await message.answer(t(lang, "menu"), reply_markup=keyboards.main_kb(lang))


@router.message(Command("about"))
async def about_command(message: Message) -> None:
    user = await store.get_user(message.from_user.id)
    lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
    await message.answer(t(lang, "about"), reply_markup=keyboards.main_kb(lang))


@router.callback_query(F.data == "nav:menu")
async def nav_menu(callback: CallbackQuery) -> None:
    _, lang = await _user(callback)
    await callback.answer()
    await _edit(callback, t(lang, "menu"), keyboards.main_kb(lang))


@router.callback_query(F.data == "nav:about")
async def nav_about(callback: CallbackQuery) -> None:
    _, lang = await _user(callback)
    await callback.answer()
    await _edit(callback, t(lang, "about"), keyboards.main_kb(lang))


@router.callback_query(F.data == "nav:premium")
async def show_paywall(callback: CallbackQuery) -> None:
    user, lang = await _user(callback)
    if not user:
        return await callback.answer("/start", show_alert=True)
    market = default_market(lang)
    text = paywall_text(lang, market)
    tier = _tier(user)
    if tier != "free":
        text = f"Current plan: <b>{tier.title()}</b> until <b>{str(user.get('premium_until'))[:10]}</b>\n\n{text}"
    await store.track_event(callback.from_user.id, "paywall_view", {
        "market": market,
        "tier": tier,
        "variant": user.get("pricing_variant", "control"),
    })
    await callback.answer()
    await _edit(callback, text, keyboards.premium_kb(lang, market, bool(user.get("subscription_recurring"))))


@router.callback_query(F.data.startswith("pay:"))
async def create_checkout(callback: CallbackQuery, bot: Bot) -> None:
    product_code = callback.data.split(":", 1)[1]
    if product_code not in PRODUCTS:
        return await callback.answer("Unknown plan", show_alert=True)
    user, lang = await _user(callback)
    if not user:
        return await callback.answer("/start", show_alert=True)
    market = default_market(lang)
    product = PRODUCTS[product_code]
    amount = price(market, product_code)
    payload = make_payload(callback.from_user.id, product_code, market)
    kwargs = {
        "title": f"Vika {product.title}"[:32],
        "description": (
            f"{product.title}: {entitlements(product.tier).daily_messages} messages/day, "
            "expanded memory and premium response quality."
        )[:255],
        "payload": payload,
        "provider_token": "",
        "currency": "XTR",
        "prices": [LabeledPrice(label=product.title, amount=amount)],
    }
    if product.recurring:
        kwargs["subscription_period"] = SUBSCRIPTION_PERIOD
    invoice_url = await bot.create_invoice_link(**kwargs)
    await store.track_event(
        callback.from_user.id,
        "checkout_created",
        {"product": product_code, "market": market, "amount": amount},
    )
    await callback.answer()
    await callback.message.answer(
        f"<b>{product.title}</b> · {amount} ⭐" + (" every 30 days" if product.recurring else " one payment"),
        reply_markup=keyboards.checkout_kb(invoice_url, product_code, lang),
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    parsed = parse_payload(query.invoice_payload, query.from_user.id)
    valid = False
    if parsed and query.currency == "XTR":
        product, market = parsed
        valid = query.total_amount == price(market, product.code)
    await query.answer(ok=valid, error_message=None if valid else "Invoice data is no longer valid.")


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot) -> None:
    payment = message.successful_payment
    parsed = parse_payload(payment.invoice_payload, message.from_user.id)
    if not parsed or payment.currency != "XTR":
        logger.warning("Rejected unexpected successful payment for user %s", message.from_user.id)
        return
    product, market = parsed
    expected_amount = price(market, product.code)
    if payment.total_amount != expected_amount:
        logger.warning("Rejected payment amount mismatch for user %s", message.from_user.id)
        return
    user = await store.get_user(message.from_user.id)
    lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
    previous_charge = (user or {}).get("subscription_charge_id")
    previous_recurring = bool((user or {}).get("subscription_recurring"))
    is_first_recurring = bool(getattr(payment, "is_first_recurring", False))
    replaces_previous = not product.recurring or is_first_recurring
    if replaces_previous and previous_charge and previous_recurring and previous_charge != payment.telegram_payment_charge_id:
        try:
            await bot.edit_user_star_subscription(message.from_user.id, previous_charge, is_canceled=True)
        except Exception:
            logger.warning("Could not cancel the previous subscription for user %s", message.from_user.id)
    result = await store.record_payment(
        message.from_user.id,
        payment.telegram_payment_charge_id,
        payment.invoice_payload,
        payment.total_amount,
        product.tier,
        market,
        product.duration_days,
        product.recurring,
        payment.subscription_expiration_date.isoformat() if payment.subscription_expiration_date else None,
    )
    await store.track_event(
        message.from_user.id,
        "payment_success",
        {"product": product.code, "market": market, "amount": expected_amount, "recurring": product.recurring},
    )
    until = str(result.get("premium_until", ""))[:10]
    text = f"<b>{product.title} activated.</b>\nAccess is active until {until}."
    if settings.private_channel_url:
        text += f"\n\nPrivate community: {html.escape(settings.private_channel_url)}"
    await message.answer(text, reply_markup=keyboards.main_kb(lang))


@router.message(F.refunded_payment)
async def refunded_payment(message: Message) -> None:
    payment = message.refunded_payment
    if not payment:
        return
    result = await store.mark_payment_refunded(payment.telegram_payment_charge_id)
    if result.get("found"):
        await store.track_event(
            message.from_user.id,
            "payment_refunded",
            {"amount": payment.total_amount, "currency": payment.currency},
        )
        user = await store.get_user(message.from_user.id)
        lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
        await message.answer("Payment refunded. The related paid access has been updated.", reply_markup=keyboards.main_kb(lang))


@router.callback_query(F.data == "subscription:manage")
async def subscription_manage(callback: CallbackQuery) -> None:
    user, lang = await _user(callback)
    if not user or not user.get("subscription_recurring"):
        return await callback.answer("No active recurring subscription", show_alert=True)
    status = "canceled" if user.get("subscription_canceled") else "renews automatically"
    text = (
        f"<b>{_tier(user).title()}</b> · {status}\n"
        f"Current access remains active until {str(user.get('premium_until'))[:10]}."
    )
    await callback.answer()
    await _edit(callback, text, keyboards.subscription_kb(lang, not bool(user.get("subscription_canceled"))))


@router.callback_query(F.data == "subscription:cancel")
async def subscription_cancel(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _user(callback)
    charge_id = (user or {}).get("subscription_charge_id")
    if not user or not charge_id or not user.get("subscription_recurring"):
        return await callback.answer("No active recurring subscription", show_alert=True)
    await bot.edit_user_star_subscription(callback.from_user.id, charge_id, is_canceled=True)
    await store.update_user(callback.from_user.id, subscription_canceled=True)
    await store.track_event(callback.from_user.id, "subscription_canceled", {"tier": _tier(user)})
    await callback.answer("Renewal canceled")
    await _edit(
        callback,
        f"Renewal canceled. Access remains active until {str(user.get('premium_until'))[:10]}.",
        keyboards.subscription_kb(lang, False),
    )


@router.callback_query(F.data == "subscription:resume")
async def subscription_resume(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _user(callback)
    charge_id = (user or {}).get("subscription_charge_id")
    if not user or not charge_id or not user.get("subscription_recurring"):
        return await callback.answer("No recurring subscription to resume", show_alert=True)
    await bot.edit_user_star_subscription(callback.from_user.id, charge_id, is_canceled=False)
    await store.update_user(callback.from_user.id, subscription_canceled=False)
    await store.track_event(callback.from_user.id, "subscription_resumed", {"tier": _tier(user)})
    await callback.answer("Renewal resumed")
    await _edit(
        callback,
        f"Renewal resumed. Next access date: {str(user.get('premium_until'))[:10]}.",
        keyboards.subscription_kb(lang, True),
    )


@router.message(Command("funnel"), F.from_user.id == settings.admin_id)
@router.message(Command("stats"), F.from_user.id == settings.admin_id)
async def admin_stats(message: Message) -> None:
    stats = await store.stats()
    overview = stats.get("overview", {})
    funnel = stats.get("funnel", {})
    revenue = stats.get("revenue", {})
    retention = stats.get("retention", {})
    reminders = stats.get("reminders", {})
    acquisition = stats.get("acquisition", {})
    await message.answer(
        "<b>Vika · продукт и воронка</b>\n\n"
        f"Пользователи: <b>{overview.get('users', 0)}</b> · доступно: <b>{overview.get('reachable', 0)}</b>\n"
        f"Новые: 24ч <b>{overview.get('new_1d', 0)}</b> · 7д <b>{overview.get('new_7d', 0)}</b> · 30д <b>{overview.get('new_30d', 0)}</b>\n"
        f"Активные: 24ч <b>{overview.get('active_1d', 0)}</b> · 7д <b>{overview.get('active_7d', 0)}</b> · 30д <b>{overview.get('active_30d', 0)}</b>\n"
        f"Сообщений пользователей: <b>{overview.get('messages', 0)}</b>\n\n"
        "<b>Воронка</b>\n"
        f"Start: <b>{funnel.get('started', 0)}</b>\n"
        f"Начали чат: <b>{funnel.get('chatted', 0)}</b> · {funnel.get('chatted_pct', 0)}%\n"
        f"3+ сообщения: <b>{funnel.get('engaged_3', 0)}</b> · {funnel.get('engaged_3_pct', 0)}%\n"
        f"10+ сообщений: <b>{funnel.get('engaged_10', 0)}</b> · {funnel.get('engaged_10_pct', 0)}%\n"
        f"Показы CTA Premium/канала: <b>{funnel.get('premium_nudges', 0)}/{funnel.get('channel_nudges', 0)}</b>\n"
        f"Открыли Premium: <b>{funnel.get('paywall_users', 0)}</b>\n"
        f"Создали оплату: <b>{funnel.get('checkout_users', 0)}</b> · из paywall {funnel.get('paywall_to_checkout_pct', 0)}%\n"
        f"Заплатили: <b>{funnel.get('payer_users', 0)}</b> · из checkout {funnel.get('checkout_to_paid_pct', 0)}%\n"
        f"Start → paid: <b>{funnel.get('start_to_paid_pct', 0)}%</b> · Premium сейчас: <b>{funnel.get('premium_active', 0)}</b>"
    )
    await message.answer(
        "<b>Vika · деньги и удержание</b>\n\n"
        f"Выручка: <b>{revenue.get('stars', 0)} ⭐</b> · платежей: <b>{revenue.get('payments', 0)}</b>\n"
        f"Плательщиков: <b>{revenue.get('payers', 0)}</b> · ARPPU: <b>{revenue.get('arppu_stars', 0)} ⭐</b>\n"
        f"Возвраты: <b>{revenue.get('refunds', 0)}</b> · {revenue.get('refund_pct', 0)}%\n"
        f"Отменили продление: <b>{revenue.get('canceled_subscriptions', 0)}</b> · Black: <b>{revenue.get('black_purchases', 0)}</b>\n"
        f"Тарифы: {_format_breakdown(revenue.get('tiers'))}\n"
        f"Выручка по рынкам: {_format_breakdown(revenue.get('markets'))}\n\n"
        "<b>Retention</b>\n"
        f"D1: <b>{retention.get('d1_returned', 0)}/{retention.get('d1_eligible', 0)}</b> · {retention.get('d1_pct', 0)}%\n"
        f"D3: <b>{retention.get('d3_returned', 0)}/{retention.get('d3_eligible', 0)}</b> · {retention.get('d3_pct', 0)}%\n"
        f"D7: <b>{retention.get('d7_returned', 0)}/{retention.get('d7_eligible', 0)}</b> · {retention.get('d7_pct', 0)}%\n\n"
        "<b>Напоминания</b>\n"
        f"D1/D3/D7 отправлено: <b>{reminders.get('d1_sent', 0)}/{reminders.get('d3_sent', 0)}/{reminders.get('d7_sent', 0)}</b>\n"
        f"Возвраты: <b>{reminders.get('returned', 0)}</b> · пользователей <b>{reminders.get('returned_users', 0)}</b> · {reminders.get('return_pct', 0)}%\n\n"
        f"Источники: {_format_breakdown(acquisition.get('refs'))}\n"
        f"Языки: {_format_breakdown(acquisition.get('languages'))}"
    )


@router.message(Command("broadcast"), F.from_user.id == settings.admin_id)
async def admin_broadcast(message: Message, command: CommandObject, bot: Bot) -> None:
    if not command.args:
        return await message.answer("Usage: /broadcast text")
    users = await store._request("GET", "users?blocked=eq.false&select=user_id&limit=10000")
    sent = 0
    for user in users:
        try:
            await bot.send_message(user["user_id"], html.escape(command.args))
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            await store.mark_blocked(user["user_id"])
        except Exception:
            logger.exception("Broadcast failed for user %s", user["user_id"])
    await message.answer(f"Delivered: {sent}/{len(users)}")


@router.message(Command("msg"), F.from_user.id == settings.admin_id)
@router.message(Command("send"), F.from_user.id == settings.admin_id)
async def admin_send_to_user(message: Message, command: CommandObject, bot: Bot) -> None:
    raw = (command.args or "").strip()
    raw_user_id, separator, body = raw.partition(" ")
    if not raw_user_id.isdigit():
        return await message.answer("Usage: /send USER_ID text")
    if not separator or not body.strip():
        return await message.answer("Добавь текст после ID: /send USER_ID текст")
    user_id = int(raw_user_id)
    user = await store.get_user(user_id)
    if not user:
        return await message.answer("Пользователь с таким ID не найден в базе.")
    body = compact_text(body.strip(), 4000)
    until = datetime.now(timezone.utc) + timedelta(minutes=settings.human_takeover_minutes)
    try:
        await bot.send_message(user_id, body, parse_mode=None)
        await store.add_message(user_id, "assistant", body)
        await store.update_user(user_id, human_takeover_until=until.isoformat())
        await store.track_event(
            user_id,
            "admin_direct_message",
            {"takeover_minutes": settings.human_takeover_minutes},
        )
        await message.answer(
            f"Отправлено пользователю <code>{user_id}</code>. "
            f"AI приостановлен на {settings.human_takeover_minutes} минут."
        )
    except TelegramForbiddenError:
        await store.mark_blocked(user_id)
        await message.answer("Пользователь заблокировал бота.")
    except TelegramBadRequest as exc:
        await message.answer(f"Telegram отклонил сообщение: {html.escape(str(exc))}")


@router.message(Command("pause"), F.from_user.id == settings.admin_id)
async def admin_pause_ai(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").split()
    if not parts or not parts[0].isdigit():
        return await message.answer("Usage: /pause USER_ID [MINUTES]")
    user_id = int(parts[0])
    minutes = settings.human_takeover_minutes
    if len(parts) > 1 and parts[1].isdigit():
        minutes = max(1, min(int(parts[1]), 1440))
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    await store.update_user(user_id, human_takeover_until=until.isoformat())
    await store.track_event(user_id, "human_takeover_started", {"minutes": minutes})
    await message.answer(f"AI paused for {user_id} until {until:%H:%M UTC}.")


@router.message(Command("ai"), F.from_user.id == settings.admin_id)
async def admin_resume_ai(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit():
        return await message.answer("Usage: /ai USER_ID")
    user_id = int(raw)
    await store.update_user(user_id, human_takeover_until=None)
    await store.track_event(user_id, "human_takeover_ended")
    await message.answer(f"AI resumed for {user_id}.")


@router.message(F.reply_to_message & F.text, F.from_user.id == settings.admin_id)
async def admin_ticket_reply(message: Message, bot: Bot) -> None:
    source = message.reply_to_message.text or ""
    match = re.search(r"TICKET_ID:\s*(\d+)", source)
    if not match:
        return
    user_id = int(match.group(1))
    until = datetime.now(timezone.utc) + timedelta(minutes=settings.human_takeover_minutes)
    try:
        await bot.send_message(user_id, message.text, parse_mode=None)
        await store.add_message(user_id, "assistant", compact_text(message.text, 4000))
        await store.update_user(user_id, human_takeover_until=until.isoformat())
        await store.track_event(
            user_id,
            "admin_reply",
            {"takeover_minutes": settings.human_takeover_minutes},
        )
        await message.reply(
            f"Delivered. AI paused for {settings.human_takeover_minutes} minutes. "
            f"Use /ai {user_id} to resume earlier."
        )
    except TelegramForbiddenError:
        await store.mark_blocked(user_id)
        await message.reply("User blocked the bot.")


@router.message(F.text & ~F.text.startswith("/"))
async def chat(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    if user_id == settings.admin_id:
        return
    async with _lock(user_id):
        user = await store.get_user(user_id)
        lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
        if not user or not user.get("onboarding_complete"):
            return await message.answer(t(lang, "not_ready"))
        user_text = compact_text(message.text or "", 4000)
        if not user_text:
            return
        try:
            reminder_stage = int(user.get("reminder_stage") or 0)
            takeover_active = _takeover_active(user)
            if takeover_active or _is_hot_lead(user_text):
                await _notify_admin(message, bot, user, user_text)
                if not takeover_active:
                    await store.track_event(user_id, "hot_lead", {"tier": _tier(user), "lang": lang})
            history = await store.recent_messages(user_id, entitlements(_tier(user)).history_messages)
            await store.add_message(user_id, "user", user_text)
            if takeover_active:
                await store.update_user(
                    user_id,
                    last_active_at=datetime.now(timezone.utc).isoformat(),
                    last_reminder_at=None,
                    reminder_stage=0,
                )
                if reminder_stage:
                    await store.track_event(
                        user_id,
                        "reminder_returned",
                        {"stage": f"d{(1, 3, 7)[reminder_stage - 1]}"},
                    )
                await store.track_event(user_id, "message_during_human_takeover")
                return
            tier = _tier(user)
            limits = entitlements(tier)
            quota = await store.consume_quota(user_id, limits.daily_messages)
            if reminder_stage:
                await store.track_event(
                    user_id,
                    "reminder_returned",
                    {"stage": f"d{(1, 3, 7)[reminder_stage - 1]}"},
                )
            if not quota.get("allowed"):
                await store.track_event(user_id, "quota_paywall", {"tier": tier})
                return await message.answer(
                    f"Daily {tier.title()} limit reached. Choose a higher plan for more messages.",
                    reply_markup=keyboards.premium_kb(lang, default_market(lang), bool(user.get("subscription_recurring"))),
                )
            memories = await store.memories(user_id, limits.memories)
            level, _ = relationship_level(int(quota.get("xp", user.get("xp", 0))))
            await bot.send_chat_action(user_id, "typing")
            reply = await companion_ai.reply(
                lang=lang,
                style=user.get("style", "warm"),
                level=level,
                memories=memories,
                history=history,
                user_text=user_text,
                model=limits.model,
            )
            if not reply:
                return await message.answer(t(lang, "ai_error"))
            total = int(quota.get("total_messages", 0))
            rendered_reply = html.escape(reply)
            nudge_event = ""
            if tier == "free" and total in {4, 12, 30}:
                rendered_reply += f"\n\n{t(lang, 'premium_nudge')}"
                nudge_event = "premium_nudge_shown"
            elif settings.public_channel(lang) and total in {7, 20, 50}:
                rendered_reply += f"\n\n{t(lang, 'channel_nudge')}"
                nudge_event = "channel_nudge_shown"
            await store.add_message(user_id, "assistant", reply)
            await message.answer(rendered_reply, reply_markup=keyboards.main_kb(lang))
            if nudge_event:
                await store.track_event(user_id, nudge_event, {"message_count": total})
            if total in {1, 3, 10, 25, 50, 100}:
                await store.track_event(user_id, "message_milestone", {"count": total, "tier": tier})
            if total and total % settings.memory_extraction_interval == 0:
                items = await companion_ai.extract_memories(user_text)
                await store.upsert_memories(user_id, items)
        except DatabaseError:
            logger.exception("Database error while chatting with user %s", user_id)
            await message.answer(t(lang, "ai_error"))
        except Exception:
            logger.exception("Chat generation failed for user %s", user_id)
            await message.answer(t(lang, "ai_error"))
