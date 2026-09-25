import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, ChatJoinRequest, LabeledPrice, Message, PreCheckoutQuery

import keyboards
from ai_companion import companion_ai
from config import settings
from database import DatabaseError, store
from domain import compact_text, normalize_lang, premium_is_active, relationship_level
from monetization import (
    PRODUCTS,
    MARKETS,
    SUBSCRIPTION_PERIOD,
    billing_period_text,
    default_market,
    entitlements,
    invoice_description,
    make_payload,
    parse_payload,
    paywall_text,
    price,
    product_title,
)
from texts import t

router = Router()
logger = logging.getLogger(__name__)
_user_locks: dict[int, asyncio.Lock] = {}


@router.channel_post(Command("channel_id"))
async def channel_id_command(message: Message, bot: Bot) -> None:
    if settings.admin_id:
        await bot.send_message(settings.admin_id, f"Channel ID: <code>{message.chat.id}</code> — use this number as PRIVATE_CHANNEL_URL")


async def _channel_id(bot: Bot) -> int | None:
    if not settings.private_channel_ref:
        return None
    try:
        chat = await bot.get_chat(settings.private_channel_ref)
        return chat.id
    except Exception:
        logger.exception("Could not resolve PRIVATE_CHANNEL_URL to a channel ID")
        return None


async def _channel_ready(bot: Bot) -> bool:
    channel_id = await _channel_id(bot)
    if not channel_id:
        return False
    try:
        member = await bot.get_chat_member(channel_id, bot.id)
        return str(member.status) in {"administrator", "creator"} and (
            str(member.status) == "creator" or
            bool(getattr(member, "can_invite_users", False) and getattr(member, "can_restrict_members", False))
        )
    except Exception:
        logger.exception("Could not verify private channel permissions")
        return False


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
    tier = _tier(user)
    priority = ("🔴 PRIORITY · " if tier in {"ultra", "black"}
                else "🟠 PAID CHAT · " if tier == "pro" else "⚪ OPEN CHAT · ")
    ticket = (
        priority +
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


@router.message(Command("call"))
async def request_call(message: Message, bot: Bot) -> None:
    user = await store.get_user(message.from_user.id)
    lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
    if not user or _tier(user) != "black":
        return await message.answer(t(lang, "call_requires_plan"))
    result = await store.request_call(message.from_user.id)
    if not result.get("ok"):
        return await message.answer(t(lang, "call_limit"))
    await store.track_event(message.from_user.id, "call_requested", {"request_id": result["id"]})
    await message.answer(t(lang, "call_requested"))
    if settings.admin_id:
        await bot.send_message(settings.admin_id, f"📞 Call request <code>{result['id']}</code> · user <code>{message.from_user.id}</code> · /send {message.from_user.id} [time]")


@router.message(Command("calls"), F.from_user.id == settings.admin_id)
async def admin_calls(message: Message) -> None:
    calls = await store.pending_calls()
    await message.answer("Pending calls:\n" + "\n".join(f"#{c['id']} · {c['user_id']} · {str(c['created_at'])[:16]}" for c in calls) if calls else "No pending calls.")


@router.message(Command("call_done"), F.from_user.id == settings.admin_id)
async def admin_call_done(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit():
        return await message.answer("Usage: /call_done REQUEST_ID")
    done = await store.complete_call(int(raw))
    await message.answer("Marked complete." if done else "Pending request not found.")


@router.message(Command("call_cancel"), F.from_user.id == settings.admin_id)
async def admin_call_cancel(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit():
        return await message.answer("Usage: /call_cancel REQUEST_ID")
    canceled = await store.cancel_call(int(raw))
    await message.answer("Canceled; call slot restored." if canceled else "Pending request not found.")


@router.message(Command("queue"), F.from_user.id == settings.admin_id)
async def admin_reply_queue(message: Message) -> None:
    pending = await store.reply_queue()
    entries = []
    for row in pending:
        user = await store.get_user(row["user_id"])
        tier = _tier(user)
        entries.append((0 if tier in {"black", "ultra"} else 1 if tier == "pro" else 2,
                        f"{_tier(user)} · {row['user_id']} · {str(row['updated_at'])[:16]}"))
    entries.sort()
    await message.answer("Pending replies:\n" + "\n".join(item for _, item in entries) if entries else "No pending replies.")


@router.message(Command("paysupport"))
async def payment_support(message: Message, bot: Bot) -> None:
    user = await store.get_user(message.from_user.id)
    lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
    if settings.admin_id:
        await bot.send_message(settings.admin_id, f"Payment support · <code>{message.from_user.id}</code> · /send {message.from_user.id} [answer]")
    await message.answer(t(lang, "payment_support"))


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
    lang = user["lang"]
    await store.track_event(message.from_user.id, "start", {"ref": ref, "lang": lang, "market": user.get("market")})
    if not user.get("region_confirmed"):
        await message.answer(t(lang, "region_prompt"), reply_markup=keyboards.region_confirm_kb(lang, user["market"]))
        return
    safe_name = html.escape(message.from_user.first_name or "")
    await message.answer(t(lang, "welcome", name=safe_name), reply_markup=keyboards.main_kb(lang))


@router.callback_query(F.data == "region:choose")
async def choose_region(callback: CallbackQuery) -> None:
    user, lang = await _user(callback)
    if not user or user.get("region_confirmed"):
        return await callback.answer(t(lang, "region_already_set"), show_alert=True)
    await callback.answer()
    await _edit(callback, t(lang, "region_choose"), keyboards.region_choose_kb())


@router.callback_query(F.data.startswith("region:set:"))
async def set_region(callback: CallbackQuery) -> None:
    user, lang = await _user(callback)
    market = callback.data.removeprefix("region:set:")
    if not user or user.get("region_confirmed") or market not in MARKETS:
        return await callback.answer(t(lang, "region_already_set"), show_alert=True)
    saved = await store.confirm_region(callback.from_user.id, market)
    if not saved:
        return await callback.answer(t(lang, "region_already_set"), show_alert=True)
    await store.track_event(callback.from_user.id, "onboarding_completed", {"market": market})
    await callback.answer()
    await _edit(callback, t(lang, "welcome", name=html.escape(callback.from_user.first_name or "")), keyboards.main_kb(lang))


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
    if not user.get("region_confirmed"):
        return await callback.answer(t(lang, "region_first"), show_alert=True)
    market = user["market"]
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
    if not user.get("region_confirmed"):
        return await callback.answer(t(lang, "region_first"), show_alert=True)

    if not await _channel_ready(bot):
        return await callback.answer(t(lang, "channel_unavailable"), show_alert=True)
    market = user["market"]
    product = PRODUCTS[product_code]
    display_title = product_title(lang, product_code)
    amount = price(market, product_code)
    payload = make_payload(callback.from_user.id, product_code, market)

    kwargs = {
        "title": f"{settings.companion_name} {display_title}"[:32],
        "description": f"{invoice_description(lang, product_code)}. {billing_period_text(lang)}."[:255],
        "payload": payload,
        "provider_token": "",
        "currency": "XTR",
        "prices": [
            LabeledPrice(
                label=display_title,
                amount=amount,
            )
        ],
    }

    if product.recurring:
        kwargs["subscription_period"] = SUBSCRIPTION_PERIOD

    invoice_url = await bot.create_invoice_link(**kwargs)

    await store.track_event(
        callback.from_user.id,
        "checkout_created",
        {
            "product": product_code,
            "market": market,
            "amount": amount,
        },
    )

    await callback.answer()

    await callback.message.answer(
        f"<b>{html.escape(display_title)}</b> · {amount} ⭐"
        + f" · {billing_period_text(lang)}",
        reply_markup=keyboards.checkout_kb(
            invoice_url,
            product_code,
            lang,
        ),
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, bot: Bot) -> None:
    parsed = parse_payload(query.invoice_payload, query.from_user.id)
    valid = False
    if parsed and query.currency == "XTR":
        product, market = parsed
        valid = query.total_amount == price(market, product.code) and await _channel_ready(bot)
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
    display_title = product_title(lang, product.code)
    text = (
        f"<b>{html.escape(display_title)} activated.</b>\n"
        f"Access is active until {until}."
    )
    channel_id = await _channel_id(bot)
    if channel_id:
        try:
            invite = await bot.create_chat_invite_link(
                channel_id, name=f"paid-{message.from_user.id}",
                expire_date=datetime.now(timezone.utc) + timedelta(days=1),
                creates_join_request=True,
            )
            text += f"\n\n{t(lang, 'channel_join')}: {html.escape(invite.invite_link)}"
        except Exception:
            logger.exception("Unable to create invite for buyer %s", message.from_user.id)
            text += f"\n\n{t(lang, 'channel_unavailable')}"
    else:
        text += f"\n\n{t(lang, 'channel_unavailable')}"
    await message.answer(text, reply_markup=keyboards.main_kb(lang))


@router.chat_join_request()
async def paid_channel_join(request: ChatJoinRequest, bot: Bot) -> None:
    channel_id = await _channel_id(bot)
    if not channel_id or request.chat.id != channel_id:
        return
    user = await store.get_user(request.from_user.id)
    if user and premium_is_active(user):
        await bot.approve_chat_join_request(request.chat.id, request.from_user.id)
        await store.update_user(request.from_user.id, channel_member=True)
        await store.track_event(request.from_user.id, "channel_joined", {"tier": _tier(user)})
    else:
        await bot.decline_chat_join_request(request.chat.id, request.from_user.id)


@router.message(Command("access"))
async def resend_channel_access(message: Message, bot: Bot) -> None:
    user = await store.get_user(message.from_user.id)
    lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
    if not user or not premium_is_active(user):
        return await message.answer(t(lang, "access_requires_plan"))
    if not await _channel_ready(bot):
        return await message.answer(t(lang, "channel_unavailable"))
    channel_id = await _channel_id(bot)
    if not channel_id:
        return await message.answer(t(lang, "channel_unavailable"))
    invite = await bot.create_chat_invite_link(
        channel_id, name=f"paid-{message.from_user.id}",
        expire_date=datetime.now(timezone.utc) + timedelta(days=1), creates_join_request=True,
    )
    await message.answer(f"{t(lang, 'channel_join')}: {html.escape(invite.invite_link)}")


@router.message(F.refunded_payment)
async def refunded_payment(message: Message, bot: Bot) -> None:
    payment = message.refunded_payment
    if not payment:
        return
    result = await store.mark_payment_refunded(payment.telegram_payment_charge_id)
    if result.get("found"):
        current = await store.get_user(message.from_user.id)
        if settings.private_channel_ref and not premium_is_active(current or {}):
            try:
                await remove_channel_access(bot, message.from_user.id)
            except Exception:
                logger.exception("Failed to remove channel access after refund for %s", message.from_user.id)
        await store.track_event(
            message.from_user.id,
            "payment_refunded",
            {"amount": payment.total_amount, "currency": payment.currency},
        )
        user = await store.get_user(message.from_user.id)
        lang = (user or {}).get("lang") or normalize_lang(message.from_user.language_code)
        await message.answer("Payment refunded. The related paid access has been updated.", reply_markup=keyboards.main_kb(lang))


async def remove_channel_access(bot: Bot, user_id: int) -> None:
    channel_id = await _channel_id(bot)
    if not channel_id:
        raise RuntimeError("Cannot remove channel access: configure a resolvable PRIVATE_CHANNEL_URL")
    await bot.ban_chat_member(channel_id, user_id)
    await bot.unban_chat_member(channel_id, user_id, only_if_banned=True)
    await store.update_user(user_id, channel_member=False)
    await store.track_event(user_id, "channel_access_ended")


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
    membership = stats.get("membership", {})
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
        f"Открыли тарифы: <b>{funnel.get('paywall_users', 0)}</b>\n"
        f"Создали оплату: <b>{funnel.get('checkout_users', 0)}</b> · из paywall {funnel.get('paywall_to_checkout_pct', 0)}%\n"
        f"Заплатили: <b>{funnel.get('payer_users', 0)}</b> · из checkout {funnel.get('checkout_to_paid_pct', 0)}%\n"
        f"Start → paid: <b>{funnel.get('start_to_paid_pct', 0)}%</b> · Доступ сейчас: <b>{funnel.get('premium_active', 0)}</b>\n"
        f"В канале: <b>{membership.get('channel_members', 0)}</b> · заявок принято: <b>{membership.get('joined', 0)}</b>"
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
        f"Языки: {_format_breakdown(acquisition.get('languages'))}\n\n"
        f"Очередь чата: <b>{membership.get('reply_queue', 0)}</b> · автоответов: <b>{membership.get('delayed_replies', 0)}</b>\n"
        f"Звонки: ожидают <b>{membership.get('call_pending', 0)}</b> · проведены <b>{membership.get('call_completed', 0)}</b>"
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
        await store.clear_pending_reply(user_id)
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
        await store.clear_pending_reply(user_id)
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
        lang = (user or {}).get("lang") or normalize_lang(
            message.from_user.language_code
        )

        if not user or not user.get("onboarding_complete"):
            return await message.answer(t(lang, "not_ready"))

        user_text = compact_text(message.text or "", 4000)
        if not user_text:
            return

        try:
            reminder_stage = int(user.get("reminder_stage") or 0)
            takeover_active = _takeover_active(user)

            # Каждое сообщение пользователя отправляется админу
            await _notify_admin(message, bot, user, user_text)

            if _is_hot_lead(user_text):
                await store.track_event(
                    user_id,
                    "hot_lead",
                    {
                        "tier": _tier(user),
                        "lang": lang,
                    },
                )

            await store.add_message(user_id, "user", user_text)
            await store.record_chat_activity(user_id)
            if reminder_stage:
                await store.track_event(
                    user_id, "reminder_returned",
                    {"stage": f"d{(1, 3, 7)[reminder_stage - 1]}"},
                )
            if not takeover_active:
                await store.queue_reply(user_id)
            await store.track_event(user_id, "chat_message", {"tier": _tier(user)})

        except DatabaseError:
            logger.exception(
                "Database error while chatting with user %s",
                user_id,
            )
            await message.answer(t(lang, "ai_error"))

        except Exception:
            logger.exception(
                "Chat generation failed for user %s",
                user_id,
            )
            await message.answer(t(lang, "ai_error"))
