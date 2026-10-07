from __future__ import annotations

import asyncio
import html
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, ChatJoinRequest, ChatMemberUpdated, ForceReply, LabeledPrice, Message, PreCheckoutQuery

import keyboards
from config import settings
from channel_access import (
    ChannelAccessError,
    channel_capabilities,
    private_access_available,
    private_channel_id,
    private_join_url,
    public_join_url,
)
from database import DatabaseError, store
from domain import compact_text, normalize_lang, premium_is_active, normalize_partner_code, partner_ref, partner_code_from_ref
from monetization import (
    CHECKOUT_TTL_SECONDS,
    MARKETS,
    PRODUCTS,
    SUBSCRIPTION_PERIOD,
    billing_period_text,
    default_market,
    make_payload,
    parse_payload,
    parse_payment_details,
    amount_matches_invoice,
    paywall_text,
    price,
    product_description,
    product_title,
)
from sales_copy import quick_reply
from texts import t

router = Router()
logger = logging.getLogger(__name__)
_user_locks: dict[int, asyncio.Lock] = {}

LANGS = {"uk", "ru", "en", "de", "fr", "es"}
CHECKOUT_JOB_TYPES = ["checkout_5m", "checkout_10m", "checkout_30m", "checkout_3h", "checkout_12h", "checkout_23h", "checkout_daily"]
OFFER_JOB_TYPES = ["offer_3h", "offer_12h", "offer_48h", "offer_daily"]
COLD_JOB_TYPES = ["cold_6h", "cold_24h", "cold_daily"]
SERVICE_JOB_TYPES = ["buyer_checkin_10m"]
MARKETING_JOB_TYPES = COLD_JOB_TYPES + OFFER_JOB_TYPES + CHECKOUT_JOB_TYPES
# v9: event-driven reminders only. No generic cold campaign in limited mode.
LIMITED_REMINDER_JOB_TYPES = {"gate_6h", "offer_3h", "checkout_10m", "checkout_12h", "buyer_checkin_10m"}



def _lock(user_id: int) -> asyncio.Lock:
    return _user_locks.setdefault(user_id, asyncio.Lock())


def _tier(user: dict | None) -> str:
    if not user or not premium_is_active(user):
        return "free"
    return str(user.get("subscription_tier") or "plus")


def _format_breakdown(value: object) -> str:
    if not isinstance(value, dict) or not value:
        return "—"
    return ", ".join(f"{html.escape(str(k))}: <b>{html.escape(str(v))}</b>" for k, v in value.items())


def _member_status(member: object) -> bool:
    raw = getattr(member, "status", "")
    status = getattr(raw, "value", str(raw)).lower().split(".")[-1]
    if status in {"member", "administrator", "creator"}:
        return True
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False


def _main_kb(user: dict, lang: str):
    tier = _tier(user)
    return keyboards.main_kb(lang, paid=tier != "free", tier=tier)


async def _private_channel_id(bot: Bot) -> int | None:
    return await private_channel_id(bot)


async def _private_channel_ready(bot: Bot) -> bool:
    caps = await channel_capabilities(bot, settings.private_channel_ref)
    return bool(caps.resolvable and caps.can_invite)


def _static_private_link() -> str | None:
    # Kept only for backwards compatibility in admin/debug code. Actual access
    # delivery is delegated to channel_access.private_join_url().
    value = (settings.private_channel_url or "").strip()
    if value.startswith(("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/")):
        return value
    return None


async def _private_access_available(bot: Bot) -> bool:
    return await private_access_available(bot)


async def _create_private_invite(bot: Bot, user_id: int) -> str | None:
    return await private_join_url(bot, user_id)


async def _public_gate_markup(bot: Bot, lang: str, user_id: int):
    """Build a safe keyboard for public/private mandatory channels.

    When PUB_LINK_* contains a private -100... chat id, Telegram creates a fresh
    one-user invite link instead of trying to use that id as a URL button.
    A permission/configuration problem never produces an invalid Telegram button.
    """
    try:
        join_url = await public_join_url(bot, lang, user_id)
    except Exception:
        logger.exception("Could not create mandatory-channel invite lang=%s user=%s", lang, user_id)
        join_url = None
    return keyboards.public_gate_kb(lang, join_url=join_url)


async def _public_membership(bot: Bot, user_id: int, lang: str) -> tuple[bool, bool]:
    """Return (member, verification_available). Public channel links are enough if public."""
    ref = settings.public_channel_ref(lang)
    if not ref:
        return False, False
    try:
        member = await bot.get_chat_member(ref, user_id)
        return _member_status(member), True
    except Exception:
        logger.exception("Public-channel check failed lang=%s user=%s ref=%r", lang, user_id, ref)
        return False, False


async def _schedule_gate_followup(user_id: int, lang: str) -> None:
    if not settings.followups_enabled:
        return
    now = datetime.now(timezone.utc)
    await store.schedule_job(
        user_id,
        "gate_6h",
        (now + timedelta(hours=6)).isoformat(),
        f"gate:{user_id}:{lang}:{now.date().isoformat()}",
        {"lang": lang, "origin_at": now.isoformat()},
    )


async def _schedule_offer_followups(user_id: int, market: str) -> None:
    if not settings.followups_enabled:
        return
    now = datetime.now(timezone.utc)
    offer_id = uuid.uuid4().hex[:12]
    await store.cancel_jobs(user_id, OFFER_JOB_TYPES)
    payload = {"origin_at": now.isoformat(), "market": market, "offer_id": offer_id}
    if settings.marketing_mode == "limited":
        # One decision-support reminder while the offer is still fresh.
        await store.schedule_job(user_id, "offer_3h", (now + timedelta(hours=3)).isoformat(), f"offer:{offer_id}:3h", payload)
        return
    await store.schedule_job(user_id, "offer_12h", (now + timedelta(hours=12)).isoformat(), f"offer:{offer_id}:12h", payload)
    await store.schedule_job(user_id, "offer_48h", (now + timedelta(hours=48)).isoformat(), f"offer:{offer_id}:48h", payload)
    daily = dict(payload)
    daily["day"] = 3
    await store.schedule_job(user_id, "offer_daily", (now + timedelta(hours=72)).isoformat(), f"offer:{offer_id}:daily:3", daily)


async def _schedule_cold_followups(user_id: int) -> None:
    """Always-on reactivation for free users who have not opened the offer yet.

    The initial series is 6h -> 24h -> 48h, then one reminder every 24h.
    Stable dedupe keys keep repeated /start/menu actions from creating duplicates.
    """
    if not settings.followups_enabled:
        return
    # v9 deliberately disables generic cold reactivation in the default mode.
    # Historical cold_daily sent 247 messages with zero attributed payments.
    if settings.marketing_mode == "limited":
        return
    now = datetime.now(timezone.utc)
    payload = {"origin_at": now.isoformat(), "day": 0}
    if settings.marketing_mode == "legacy":
        await store.schedule_job(
            user_id, "cold_6h", (now + timedelta(hours=6)).isoformat(),
            f"cold:{user_id}:initial:6h", payload,
        )
    await store.schedule_job(
        user_id, "cold_24h", (now + timedelta(hours=24)).isoformat(),
        f"cold:{user_id}:initial:24h", payload,
    )
    if settings.marketing_mode == "limited":
        return
    first_daily_at = now + timedelta(hours=48)
    daily = dict(payload)
    daily["day"] = 1
    await store.schedule_job(
        user_id, "cold_daily", first_daily_at.isoformat(),
        f"cold:{user_id}:{first_daily_at.date().isoformat()}", daily,
    )


async def _show_gate_message(message: Message, bot: Bot, lang: str) -> None:
    await store.update_user(message.from_user.id, sales_stage="channel_required")
    await store.track_event(message.from_user.id, "public_gate_shown", {"lang": lang})
    await message.answer(t(lang, "public_gate"), reply_markup=await _public_gate_markup(bot, lang, message.from_user.id))
    try:
        await _schedule_gate_followup(message.from_user.id, lang)
    except Exception:
        logger.exception("Could not schedule public-gate follow-up for %s", message.from_user.id)


async def _show_gate_callback(callback: CallbackQuery, bot: Bot, lang: str) -> None:
    await store.update_user(callback.from_user.id, sales_stage="channel_required")
    await store.track_event(callback.from_user.id, "public_gate_shown", {"lang": lang})
    if callback.message:
        try:
            await callback.message.edit_text(t(lang, "public_gate"), reply_markup=await _public_gate_markup(bot, lang, callback.from_user.id))
        except TelegramBadRequest:
            await callback.message.answer(t(lang, "public_gate"), reply_markup=await _public_gate_markup(bot, lang, callback.from_user.id))
    try:
        await _schedule_gate_followup(callback.from_user.id, lang)
    except Exception:
        logger.exception("Could not schedule public-gate follow-up for %s", callback.from_user.id)


async def _ensure_public_for_message(message: Message, bot: Bot, user: dict) -> bool:
    lang = str(user.get("lang") or normalize_lang(message.from_user.language_code))
    is_member, can_verify = await _public_membership(bot, message.from_user.id, lang)
    cached = bool(user.get("public_channel_member")) and user.get("public_channel_lang") == lang
    if is_member:
        await store.set_public_membership(message.from_user.id, True, lang)
        if not cached:
            await store.track_event(message.from_user.id, "public_channel_verified", {"lang": lang, "source": "auto"})
        await store.cancel_jobs(message.from_user.id, ["gate_6h"])
        return True
    if not can_verify and cached:
        # A temporary Telegram API problem should not lock out someone already verified.
        await store.track_event(message.from_user.id, "public_channel_check_error_cached", {"lang": lang})
        return True
    if can_verify:
        await store.set_public_membership(message.from_user.id, False, lang)
    else:
        await store.track_event(message.from_user.id, "public_channel_config_error", {"lang": lang})
        try:
            markup = await _public_gate_markup(bot, lang, message.from_user.id)
        except Exception:
            logger.exception("Could not create public invite for %s", message.from_user.id)
            markup = keyboards.public_gate_kb(lang)
        await message.answer(t(lang, "public_unavailable"), reply_markup=markup)
        return False
    await _show_gate_message(message, bot, lang)
    return False


async def _ensure_public_for_callback(callback: CallbackQuery, bot: Bot, user: dict) -> bool:
    lang = str(user.get("lang") or normalize_lang(callback.from_user.language_code))
    is_member, can_verify = await _public_membership(bot, callback.from_user.id, lang)
    cached = bool(user.get("public_channel_member")) and user.get("public_channel_lang") == lang
    if is_member:
        await store.set_public_membership(callback.from_user.id, True, lang)
        if not cached:
            await store.track_event(callback.from_user.id, "public_channel_verified", {"lang": lang, "source": "action"})
        await store.cancel_jobs(callback.from_user.id, ["gate_6h"])
        return True
    if not can_verify and cached:
        await store.track_event(callback.from_user.id, "public_channel_check_error_cached", {"lang": lang})
        return True
    if can_verify:
        await store.set_public_membership(callback.from_user.id, False, lang)
        await callback.answer(t(lang, "public_not_member"), show_alert=True)
    else:
        await callback.answer(t(lang, "public_unavailable"), show_alert=True)
    await _show_gate_callback(callback, bot, lang)
    return False


async def _edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    if not callback.message:
        return
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=reply_markup)


async def _callback_user(callback: CallbackQuery) -> tuple[dict | None, str]:
    user = await store.get_user(callback.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(callback.from_user.language_code))
    return user, lang


async def _notify_admin(message: Message, bot: Bot, user: dict, preview: str, *, media: bool = False, paid_chat: bool = False) -> None:
    if not settings.admin_id or message.from_user.id == settings.admin_id:
        return
    username = f"@{message.from_user.username}" if message.from_user.username else "NoUsername"
    tier = _tier(user)
    if tier in {"ultra", "black"}:
        label = "🔴 PRIORITY CHAT"
    elif paid_chat and tier == "pro":
        label = "💌 PREMIUM CHAT"
    elif tier == "pro":
        label = "🟠 PRO"
    elif tier == "plus":
        label = "🟡 PAID"
    else:
        label = "⚪ LEAD"
    ticket = (
        f"{label}\n"
        f"📩 <b>TICKET_ID:</b> <code>{message.from_user.id}</code>\n"
        f"👤 {html.escape(message.from_user.first_name or 'User')} · {html.escape(username)}\n"
        f"🌐 {html.escape(str(user.get('lang') or 'en'))} · {html.escape(str(user.get('market') or 'global'))} · {html.escape(str(user.get('ref') or 'direct'))}\n"
        f"💳 {html.escape(tier)} · <code>{html.escape(str(user.get('sales_stage') or '—'))}</code>\n\n"
        f"{'📎 ' if media else ''}{html.escape(preview)}"
    )
    try:
        await bot.send_message(settings.admin_id, ticket, reply_markup=keyboards.admin_ticket_kb(message.from_user.id))
        if media:
            await bot.copy_message(settings.admin_id, message.chat.id, message.message_id)
    except Exception:
        logger.warning("Could not deliver ticket for user %s", message.from_user.id, exc_info=True)


async def _admin_payment_click(bot: Bot, callback: CallbackQuery, user: dict, product_code: str, amount: int) -> None:
    if not settings.admin_id:
        return
    username = f"@{callback.from_user.username}" if callback.from_user.username else "NoUsername"
    try:
        await bot.send_message(
            settings.admin_id,
            "⚡ <b>ГОРЯЧИЙ ЛИД · клик по оплате</b>\n"
            f"ID: <code>{callback.from_user.id}</code>\n"
            f"Юзер: {html.escape(username)}\n"
            f"Тариф: <b>{html.escape(product_title(str(user.get('lang') or 'en'), product_code))}</b> ({amount} ⭐)\n"
            f"Регион: <code>{html.escape(str(user.get('market') or 'global'))}</code>\n"
            "Если человек напишет — ответ вручную важнее любого дожима.",
            reply_markup=keyboards.admin_ticket_kb(callback.from_user.id),
        )
    except Exception:
        # Admin notifications must never break a user's checkout.
        logger.exception("Could not notify admin about payment click user=%s", callback.from_user.id)


# -------------------------- Channel utility -----------------------------

@router.channel_post(Command("channel_id"))
async def channel_id_command(message: Message, bot: Bot) -> None:
    if settings.admin_id:
        await bot.send_message(
            settings.admin_id,
            f"Channel ID: <code>{message.chat.id}</code>. Если PRIVATE_CHANNEL_URL — приватная invite-ссылка, поставь этот -100... ID туда вместо ссылки.",
        )


# ---------------------------- User flow ---------------------------------

@router.message(CommandStart())
async def start(message: Message, command: CommandObject, bot: Bot) -> None:
    lang = normalize_lang(message.from_user.language_code)
    ref = compact_text(command.args or "direct", 80)
    user = await store.upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name or "User",
        lang,
        ref,
        default_market(lang, ref),
    )
    lang = str(user.get("lang") or lang)
    await store.track_event(message.from_user.id, "start", {"ref": user.get("ref") or "direct", "incoming_ref": ref, "lang": lang, "market": user.get("market")})

    if not user.get("region_confirmed"):
        market = str(user.get("market") or default_market(lang))
        await message.answer(
            t(lang, "region_choose"),
            reply_markup=keyboards.region_choose_kb(),
        )
        return
    if not await _ensure_public_for_message(message, bot, user):
        return
    fresh = await store.get_user(message.from_user.id) or user
    await message.answer(
        t(lang, "welcome", name=html.escape(message.from_user.first_name or "")),
        reply_markup=_main_kb(fresh, lang),
    )
    if _tier(fresh) == "free" and str(fresh.get("sales_stage") or "new") in {"new", "channel_required", "channel_joined", "engaged"}:
        try:
            await _schedule_cold_followups(message.from_user.id)
        except Exception:
            logger.exception("Could not schedule cold follow-ups for %s", message.from_user.id)


@router.callback_query(F.data == "region:choose")
async def choose_region(callback: CallbackQuery) -> None:
    _, lang = await _callback_user(callback)
    await callback.answer()
    await _edit(callback, t(lang, "region_choose"), keyboards.region_choose_kb())


@router.callback_query(F.data.startswith("region:set:"))
async def set_region(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    market = callback.data.removeprefix("region:set:")
    if not user or market not in MARKETS:
        return await callback.answer("/start", show_alert=True)
    await store.set_region(callback.from_user.id, market)
    await store.track_event(callback.from_user.id, "region_changed", {"market": market})
    fresh = await store.get_user(callback.from_user.id)
    if not fresh:
        return
    if await _ensure_public_for_callback(callback, bot, fresh):
        await callback.answer(t(lang, "region_saved", region=keyboards.REGION_NAMES[market]))
        fresh = await store.get_user(callback.from_user.id) or fresh
        await _edit(callback, t(lang, "welcome", name=html.escape(callback.from_user.first_name or "")), _main_kb(fresh, lang))
        if _tier(fresh) == "free" and str(fresh.get("sales_stage") or "new") in {"new", "channel_required", "channel_joined", "engaged"}:
            try:
                await _schedule_cold_followups(callback.from_user.id)
            except Exception:
                logger.exception("Could not schedule cold follow-ups for %s", callback.from_user.id)


@router.callback_query(F.data == "public:check")
async def public_check(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user:
        return await callback.answer("/start", show_alert=True)
    is_member, can_verify = await _public_membership(bot, callback.from_user.id, lang)
    if not can_verify:
        cached = bool(user.get("public_channel_member")) and user.get("public_channel_lang") == lang
        if cached:
            await callback.answer(t(lang, "public_ok"))
            return await _edit(callback, t(lang, "welcome", name=html.escape(callback.from_user.first_name or "")), _main_kb(user, lang))
        await store.track_event(callback.from_user.id, "public_channel_config_error", {"lang": lang})
        return await callback.answer(t(lang, "public_unavailable"), show_alert=True)
    if not is_member:
        await store.set_public_membership(callback.from_user.id, False, lang)
        await store.track_event(callback.from_user.id, "public_channel_verify_failed", {"lang": lang})
        return await callback.answer(t(lang, "public_not_member"), show_alert=True)

    was_member = bool(user.get("public_channel_member")) and user.get("public_channel_lang") == lang
    await store.set_public_membership(callback.from_user.id, True, lang)
    await store.cancel_jobs(callback.from_user.id, ["gate_6h"])
    if not was_member:
        await store.track_event(callback.from_user.id, "public_channel_verified", {"lang": lang, "source": "button"})
    await callback.answer(t(lang, "public_ok"))
    fresh = await store.get_user(callback.from_user.id) or user
    await _edit(callback, t(lang, "welcome", name=html.escape(callback.from_user.first_name or "")), _main_kb(fresh, lang))
    if _tier(fresh) == "free" and str(fresh.get("sales_stage") or "new") in {"new", "channel_required", "channel_joined", "engaged"}:
        try:
            await _schedule_cold_followups(callback.from_user.id)
        except Exception:
            logger.exception("Could not schedule cold follow-ups for %s", callback.from_user.id)


@router.message(Command("menu"))
async def menu_command(message: Message, bot: Bot) -> None:
    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    if not user or not user.get("region_confirmed"):
        return await message.answer(t(lang, "not_ready"))
    if not await _ensure_public_for_message(message, bot, user):
        return
    fresh = await store.get_user(message.from_user.id) or user
    await message.answer(t(lang, "menu"), reply_markup=_main_kb(fresh, lang))


@router.callback_query(F.data == "nav:menu")
async def nav_menu(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user or not await _ensure_public_for_callback(callback, bot, user):
        return
    fresh = await store.get_user(callback.from_user.id) or user
    await callback.answer()
    await _edit(callback, t(lang, "menu"), _main_kb(fresh, lang))


@router.callback_query(F.data == "nav:write")
async def nav_write(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user or not await _ensure_public_for_callback(callback, bot, user):
        return
    await callback.answer()
    if callback.message:
        await callback.message.answer(t(lang, "write_me"))


# Premium messaging is an actual dedicated bot action, not a second app/channel.
PAID_CHAT_MARKER = "💌 Premium chat"
PAID_CHAT_TIERS = {"pro", "ultra", "black"}


@router.callback_query(F.data == "nav:paid_chat")
async def nav_paid_chat(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user or not await _ensure_public_for_callback(callback, bot, user):
        return
    if _tier(user) not in PAID_CHAT_TIERS:
        return await callback.answer(t(lang, "access_requires_plan"), show_alert=True)
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            PAID_CHAT_MARKER + "\n" + t(lang, "paid_chat_prompt"),
            reply_markup=ForceReply(selective=True),
        )


def is_paid_chat_reply(message: Message, tier: str) -> bool:
    reply = message.reply_to_message
    return (tier in PAID_CHAT_TIERS and bool(reply) and
            (reply.text or "").startswith(PAID_CHAT_MARKER) and
            bool(reply.from_user) and bool(reply.from_user.is_bot))


@router.message(Command("chat"))
async def paid_chat_command(message: Message, command: CommandObject, bot: Bot) -> None:
    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    if not user or _tier(user) not in PAID_CHAT_TIERS:
        return await message.answer(t(lang, "access_requires_plan"))
    if not await _ensure_public_for_message(message, bot, user):
        return
    body = compact_text(command.args or "", 4000)
    if not body:
        return await message.answer(t(lang, "paid_chat_prompt"))
    async with _lock(message.from_user.id):
        await _receive_user_chat(message, bot, user, body, paid_chat=True)


@router.callback_query(F.data == "nav:settings")
async def nav_settings(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user or not await _ensure_public_for_callback(callback, bot, user):
        return
    await callback.answer()
    await _edit(
        callback,
        t(
            lang,
            "settings",
            region=keyboards.REGION_NAMES.get(str(user.get("market")), str(user.get("market"))),
            language=keyboards.LANG_NAMES.get(lang, lang),
        ),
        keyboards.settings_kb(lang),
    )


@router.callback_query(F.data == "settings:region")
async def settings_region(callback: CallbackQuery) -> None:
    _, lang = await _callback_user(callback)
    await callback.answer()
    await _edit(callback, t(lang, "region_choose"), keyboards.region_choose_kb())


@router.callback_query(F.data.in_({"settings:language", "settings:language_public"}))
async def settings_language(callback: CallbackQuery) -> None:
    _, lang = await _callback_user(callback)
    await callback.answer()
    await _edit(callback, t(lang, "language_choose"), keyboards.language_choose_kb())


@router.callback_query(F.data.startswith("lang:set:"))
async def set_language(callback: CallbackQuery, bot: Bot) -> None:
    user, _old_lang = await _callback_user(callback)
    lang = callback.data.removeprefix("lang:set:")
    if not user or lang not in LANGS:
        return await callback.answer("Unknown language", show_alert=True)
    await store.set_language(callback.from_user.id, lang)
    await store.cancel_jobs(callback.from_user.id, ["gate_6h"])
    await store.track_event(callback.from_user.id, "language_changed", {"lang": lang})
    fresh = await store.get_user(callback.from_user.id)
    if not fresh:
        return
    if fresh.get("region_confirmed") and await _ensure_public_for_callback(callback, bot, fresh):
        await callback.answer(t(lang, "language_saved"))
        fresh = await store.get_user(callback.from_user.id) or fresh
        await _edit(callback, t(lang, "menu"), _main_kb(fresh, lang))
    elif not fresh.get("region_confirmed"):
        market = str(fresh.get("market") or default_market(lang))
        await callback.answer(t(lang, "language_saved"))
        await _edit(callback, t(lang, "region_choose"), keyboards.region_choose_kb())


@router.message(Command("region"))
async def region_command(message: Message) -> None:
    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    await message.answer(t(lang, "region_choose"), reply_markup=keyboards.region_choose_kb())


@router.message(Command("language"))
async def language_command(message: Message) -> None:
    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    await message.answer(t(lang, "language_choose"), reply_markup=keyboards.language_choose_kb())


# ---------------------------- Sales / payment ---------------------------

@router.callback_query(F.data == "nav:premium")
async def show_paywall(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user:
        return await callback.answer("/start", show_alert=True)
    if not user.get("region_confirmed"):
        return await callback.answer(t(lang, "not_ready"), show_alert=True)
    if not await _ensure_public_for_callback(callback, bot, user):
        return

    market = str(user.get("market") or "global")
    tier = _tier(user)
    now = datetime.now(timezone.utc)
    if tier == "free":
        await store.update_user(callback.from_user.id, sales_stage="offer_seen", last_offer_at=now.isoformat())
        await store.cancel_jobs(callback.from_user.id, COLD_JOB_TYPES)
        try:
            await _schedule_offer_followups(callback.from_user.id, market)
        except Exception:
            logger.exception("Could not schedule offer follow-ups for %s", callback.from_user.id)
    await store.track_event(callback.from_user.id, "paywall_view", {"market": market, "tier": tier})

    text = paywall_text(lang, market)
    if tier != "free":
        until = str(user.get("premium_until") or "")[:10]
        current = {"uk": "Зараз у тебе", "ru": "Сейчас у тебя", "en": "Your current plan", "de": "Dein aktueller Plan", "fr": "Ta formule actuelle", "es": "Tu plan actual"}.get(lang, "Current")
        text = f"{current}: <b>{html.escape(product_title(lang, tier))}</b> · {html.escape(until)}\n\n{text}"
    await callback.answer()
    await _edit(callback, text, keyboards.premium_kb(lang, market, has_recurring=bool(user.get("subscription_recurring"))))


@router.callback_query(F.data.startswith("pay:"))
async def create_checkout(callback: CallbackQuery, bot: Bot) -> None:
    product_code = callback.data.split(":", 1)[1]
    if product_code not in PRODUCTS:
        return await callback.answer("Unknown plan", show_alert=True)
    user, lang = await _callback_user(callback)
    if not user:
        return await callback.answer("/start", show_alert=True)
    if not user.get("region_confirmed"):
        return await callback.answer(t(lang, "not_ready"), show_alert=True)
    if not await _ensure_public_for_callback(callback, bot, user):
        return
    if not await _private_access_available(bot):
        await store.track_event(callback.from_user.id, "private_channel_not_ready", {})
        return await callback.answer(t(lang, "channel_unavailable"), show_alert=True)

    market = str(user.get("market") or "global")
    product = PRODUCTS[product_code]
    display_title = product_title(lang, product_code)
    amount = price(market, product_code)
    now = datetime.now(timezone.utc)
    checkout_expires_at = now + timedelta(seconds=CHECKOUT_TTL_SECONDS)
    payload = make_payload(
        callback.from_user.id,
        product_code,
        market,
        expires_at=int(checkout_expires_at.timestamp()),
    )
    kwargs = {
        "title": f"{settings.companion_name} · {display_title}"[:32],
        "description": f"{product_description(lang, product_code)}. {billing_period_text(lang)}."[:255],
        "payload": payload,
        "provider_token": "",
        "currency": "XTR",
        "prices": [LabeledPrice(label=display_title, amount=amount)],
    }
    if product.recurring:
        kwargs["subscription_period"] = SUBSCRIPTION_PERIOD
    try:
        invoice_url = await bot.create_invoice_link(**kwargs)
    except Exception:
        logger.exception("Invoice creation failed user=%s product=%s", callback.from_user.id, product_code)
        await store.track_event(callback.from_user.id, "checkout_invoice_error", {"product": product_code})
        return await callback.answer(t(lang, "invoice_error"), show_alert=True)

    checkout_id = uuid.uuid4().hex[:12]
    await store.cancel_jobs(callback.from_user.id, MARKETING_JOB_TYPES)
    await store.update_user(callback.from_user.id, sales_stage="checkout_started", last_checkout_at=now.isoformat())
    await store.track_event(callback.from_user.id, "checkout_created", {
        "checkout_id": checkout_id,
        "product": product_code,
        "market": market,
        "amount": amount,
        "expires_at": checkout_expires_at.isoformat(),
    })

    # The checkout and admin click notification are core UX. Never make them wait
    # for the follow-up queue write; queue failures are logged separately.
    try:
        await _admin_payment_click(bot, callback, user, product_code, amount)
    except Exception:
        logger.exception("Payment click admin alert failed (checkout still works)")
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"<b>{html.escape(display_title)}</b> · {amount} ⭐\n{html.escape(billing_period_text(lang))}",
            reply_markup=keyboards.checkout_kb(invoice_url, product_code, lang),
        )

    if settings.followups_enabled:
        common = {
            "origin_at": now.isoformat(),
            "checkout_id": checkout_id,
            "product": product_code,
            "market": market,
            "amount": amount,
            "invoice_url": invoice_url,
            "checkout_expires_at": checkout_expires_at.isoformat(),
        }
        try:
            if settings.marketing_mode == "limited":
                # v9: help quickly while intent is hot, then one final same-day reminder.
                # Both are cancelled if the user pays, writes to us, or receives a manual reply.
                await store.schedule_job(callback.from_user.id, "checkout_10m", (now + timedelta(minutes=10)).isoformat(), f"checkout:{checkout_id}:10m", common)
                await store.schedule_job(callback.from_user.id, "checkout_12h", (now + timedelta(hours=12)).isoformat(), f"checkout:{checkout_id}:12h", common)
            else:
                await store.schedule_job(callback.from_user.id, "checkout_5m", (now + timedelta(minutes=5)).isoformat(), f"checkout:{checkout_id}:5m", common)
                await store.schedule_job(callback.from_user.id, "checkout_30m", (now + timedelta(minutes=30)).isoformat(), f"checkout:{checkout_id}:30m", common)
                await store.schedule_job(callback.from_user.id, "checkout_3h", (now + timedelta(hours=3)).isoformat(), f"checkout:{checkout_id}:3h", common)
                await store.schedule_job(callback.from_user.id, "checkout_12h", (now + timedelta(hours=12)).isoformat(), f"checkout:{checkout_id}:12h", common)
                await store.schedule_job(callback.from_user.id, "checkout_23h", (now + timedelta(hours=23)).isoformat(), f"checkout:{checkout_id}:23h", common)
                daily = dict(common)
                daily["day"] = 1
                await store.schedule_job(callback.from_user.id, "checkout_daily", (now + timedelta(hours=24, minutes=5)).isoformat(), f"checkout:{checkout_id}:daily:1", daily)
        except Exception:
            logger.exception("Could not schedule checkout follow-ups for %s checkout=%s", callback.from_user.id, checkout_id)
            if settings.admin_id:
                try:
                    await bot.send_message(
                        settings.admin_id,
                        "⚠️ <b>Checkout создан, но дожимы не записались</b>\n"
                        f"User: <code>{callback.from_user.id}</code> · checkout <code>{checkout_id}</code>\n"
                        "Проверь Supabase service-role key / automation_jobs.",
                    )
                except Exception:
                    logger.exception("Could not notify admin about checkout queue failure")


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, bot: Bot) -> None:
    """Acknowledge signed Stars invoice quickly (<10s). No external API calls.

    Private channel availability is validated when the invoice is generated. A
    momentary Supabase/public-channel outage must never block an already opened
    valid Telegram checkout. Access is granted only after successful_payment.
    """
    details = parse_payment_details(query.invoice_payload, query.from_user.id)
    valid = bool(details and query.currency == "XTR" and amount_matches_invoice(details, query.total_amount))
    await query.answer(
        ok=valid,
        error_message=None if valid else "Invalid or expired invoice. Please reopen checkout in the bot.",
    )


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot) -> None:
    payment = message.successful_payment
    details = parse_payment_details(payment.invoice_payload, message.from_user.id, allow_expired=True)
    if not details or payment.currency != "XTR":
        logger.error("Unrecognised confirmed Stars payment user=%s; manual reconciliation required", message.from_user.id)
        return
    product, market = details.product, details.market
    expected = payment.total_amount  # Never drop a confirmed payment because regional prices changed.
    if not amount_matches_invoice(details, expected):
        logger.error("Confirmed Stars payment has unexpected amount user=%s plan=%s amount=%s; recording paid receipt", message.from_user.id, product.code, expected)

    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    previous_charge = (user or {}).get("subscription_charge_id")
    previous_recurring = bool((user or {}).get("subscription_recurring"))
    is_first_recurring = bool(getattr(payment, "is_first_recurring", False))
    try:
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
    except Exception:
        logger.exception("CRITICAL paid charge not activated user=%s charge=%s", message.from_user.id, payment.telegram_payment_charge_id)
        if settings.admin_id:
            try:
                await bot.send_message(settings.admin_id,
                    "🚨 Stars payment received but DB activation failed!\n"
                    f"User: <code>{message.from_user.id}</code>\n"
                    f"Charge ID: <code>{html.escape(payment.telegram_payment_charge_id)}</code>\n"
                    f"Plan: <code>{product.code}</code> — {payment.total_amount} ⭐\n"
                    "Repair DB and replay this Telegram update or reconcile manually.")
            except Exception:
                logger.exception("Admin paid-charge alert also failed")
        await message.answer("Payment was received, but access activation needs support. Please contact /paysupport; your charge is recorded by Telegram.")
        return
    # Marketing/tracking operations must not delay or prevent access delivery.
    # Stop every sales reminder after payment, but keep an unanswered inbound
    # message in the admin queue. Clearing it here could make a new buyer feel
    # ignored immediately after paying.
    for action in (
        store.cancel_jobs(message.from_user.id, MARKETING_JOB_TYPES),
    ):
        try:
            await action
        except Exception:
            logger.exception("Post-payment housekeeping failed user=%s", message.from_user.id)
    # A *new* recurring checkout for the same tier must replace the first
    # charge ID; ordinary monthly renewals must keep the original ID. The
    # SQL routine cannot distinguish these from its legacy arguments alone.
    if is_first_recurring and not result.get("duplicate"):
        try:
            await store.update_user(message.from_user.id, subscription_charge_id=payment.telegram_payment_charge_id)
        except Exception:
            logger.exception("Cannot store initial subscription charge ID user=%s", message.from_user.id)
            if settings.admin_id:
                try:
                    await bot.send_message(settings.admin_id,
                        f"⚠️ Check subscription charge ID for <code>{message.from_user.id}</code> (renewal cancellation may need repair).")
                except Exception:
                    logger.exception("Could not alert admin about subscription ID repair")
    elif (not is_first_recurring and previous_recurring and previous_charge
            and not result.get("duplicate")):
        # Backwards-compatible with the currently deployed SQL RPC, which writes
        # the latest renewal charge into subscription_charge_id. Telegram expects
        # the original subscription charge ID for cancel/resume operations, so
        # restore it here without requiring a database migration.
        try:
            await store.update_user(message.from_user.id, subscription_charge_id=previous_charge)
        except Exception:
            logger.exception("Cannot restore original subscription charge ID user=%s", message.from_user.id)
            if settings.admin_id:
                try:
                    await bot.send_message(settings.admin_id,
                        f"⚠️ Не удалось восстановить ID подписки для <code>{message.from_user.id}</code>. Проверь отмену/возобновление вручную.")
                except Exception:
                    logger.exception("Could not alert admin about renewal charge ID repair")
    if (is_first_recurring and previous_charge and previous_recurring
            and previous_charge != payment.telegram_payment_charge_id and not result.get("duplicate")):
        try:
            await bot.edit_user_star_subscription(message.from_user.id, previous_charge, is_canceled=True)
        except Exception:
            logger.warning("Could not cancel previous subscription for %s", message.from_user.id, exc_info=True)
    try:
        await store.track_event(message.from_user.id, "payment_success", {
            "product": product.code,
            "market": market,
            "amount": expected,
            "recurring": product.recurring,
        })

        since = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        attributed = await store.latest_event(message.from_user.id, "sales_followup_sent", since)
        if attributed:
            await store.track_event(message.from_user.id, "followup_conversion", {
                "job_type": (attributed.get("properties") or {}).get("job_type"),
                "followup_event_id": attributed.get("id"),
                "product": product.code,
                "amount": expected,
            })

    except Exception:
        logger.exception("Optional post-payment analytics failed for %s", message.from_user.id)

    if settings.admin_id and not result.get("duplicate"):
        username = f"@{message.from_user.username}" if message.from_user.username else "NoUsername"
        try:
            await bot.send_message(
                settings.admin_id,
                "💰 <b>НОВАЯ ОПЛАТА! СРЕДСТВА ПОЛУЧЕНЫ</b>\n"
                f"Юзер: <code>{message.from_user.id}</code> · {html.escape(username)}\n"
                f"Тариф: <b>{html.escape(product_title(lang, product.code))}</b>\n"
                f"Сумма: <b>{expected} Stars</b>\n"
                f"Регион: <code>{html.escape(market)}</code>\n"
                f"✍️ Можно сразу написать покупателю вручную: <code>/send {message.from_user.id} ТЕКСТ</code>",
            )
        except Exception:
            # Access delivery after payment is more important than the admin alert.
            logger.exception("Could not notify admin about successful payment user=%s", message.from_user.id)

    # Keep traffic uploaders motivated with a real-time aggregate sale notice.
    # No customer identity or message content is disclosed to the uploader.
    if not result.get("duplicate"):
        try:
            pcode = partner_code_from_ref(str((user or {}).get("ref") or ""))
            if pcode:
                partner = await store.get_partner_by_code(pcode)
                commission = await store.partner_commission_for_charge(payment.telegram_payment_charge_id)
                if partner and commission:
                    await bot.send_message(
                        int(partner["telegram_user_id"]),
                        "💰 <b>Новая подтверждённая продажа с твоего трафика</b>\n\n"
                        f"Выручка: <b>{int(commission.get('gross_stars') or 0)} ⭐</b>\n"
                        f"Твоя комиссия: <b>+{int(commission.get('commission_stars') or 0)} ⭐</b> "
                        f"({_pct(commission.get('commission_pct'))}%)\n\n"
                        "Обновить статистику: /partner",
                    )
        except Exception:
            logger.info("Could not send partner sale notification user=%s", message.from_user.id, exc_info=True)

    until = str(result.get("premium_until") or (payment.subscription_expiration_date or ""))[:10]
    text = t(
        lang,
        "payment_success",
        plan=html.escape(product_title(lang, product.code)),
        until=html.escape(until),
        amount=expected,
    )
    invite_url = await _create_private_invite(bot, message.from_user.id)
    if invite_url:
        await message.answer(text, reply_markup=keyboards.invite_kb(lang, invite_url, tier=product.tier, recurring=product.recurring))
    else:
        await message.answer(text + "\n\n" + t(lang, "channel_unavailable"), reply_markup=_main_kb(await store.get_user(message.from_user.id) or user or {}, lang))

    # One post-purchase service check. It is not a sales nudge and is skipped when
    # the buyer already wrote to us or received a manual reply.
    if settings.followups_enabled:
        try:
            paid_at = datetime.now(timezone.utc)
            await store.schedule_job(
                message.from_user.id,
                "buyer_checkin_10m",
                (paid_at + timedelta(minutes=10)).isoformat(),
                f"buyer-checkin:{payment.telegram_payment_charge_id}:10m",
                {"origin_at": paid_at.isoformat(), "product": product.code, "market": market},
            )
        except Exception:
            logger.exception("Could not schedule buyer check-in user=%s", message.from_user.id)


@router.chat_member()
async def private_channel_member_update(event: ChatMemberUpdated, bot: Bot) -> None:
    """Track paid-channel joins via standard invite links, not only join requests.

    Without this handler, channel_member stays false and expired users will not
    appear in the scheduled access-revocation query.
    """
    channel_id = await _private_channel_id(bot)
    if channel_id is None or event.chat.id != channel_id:
        return
    uid = event.new_chat_member.user.id
    old_status = _member_status(event.old_chat_member)
    new_status = _member_status(event.new_chat_member)
    if old_status == new_status:
        return
    user = await store.get_user(uid)
    if not user:
        return
    if new_status and not premium_is_active(user):
        await bot.ban_chat_member(channel_id, uid)
        await bot.unban_chat_member(channel_id, uid, only_if_banned=True)
        await store.update_user(uid, channel_member=False)
        await store.track_event(uid, "unpaid_channel_join_blocked")
    else:
        await store.update_user(uid, channel_member=new_status)
        await store.track_event(uid, "paid_channel_member_change", {"joined": new_status})


@router.chat_join_request()
async def paid_channel_join(request: ChatJoinRequest, bot: Bot) -> None:
    channel_id = await _private_channel_id(bot)
    if not channel_id or request.chat.id != channel_id:
        return
    user = await store.get_user(request.from_user.id)
    if user and premium_is_active(user):
        await bot.approve_chat_join_request(request.chat.id, request.from_user.id)
        await store.update_user(request.from_user.id, channel_member=True)
        await store.track_event(request.from_user.id, "paid_channel_joined", {"tier": _tier(user)})
    else:
        await bot.decline_chat_join_request(request.chat.id, request.from_user.id)


async def _send_access(message_or_callback, bot: Bot, user: dict, lang: str) -> None:
    if not premium_is_active(user):
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(t(lang, "access_requires_plan"), show_alert=True)
        else:
            await message_or_callback.answer(t(lang, "access_requires_plan"))
        return
    invite_url = await _create_private_invite(bot, int(user["user_id"]))
    tier = _tier(user)
    until = str(user.get("premium_until") or "")[:10]
    text = t(lang, "activated", plan=html.escape(product_title(lang, tier)), until=html.escape(until))
    if not invite_url:
        text += "\n\n" + t(lang, "channel_unavailable")
        markup = keyboards.access_kb(lang, recurring=bool(user.get("subscription_recurring")), tier=tier)
    else:
        markup = keyboards.invite_kb(lang, invite_url, tier=tier, recurring=bool(user.get("subscription_recurring")))
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()
        await _edit(message_or_callback, text, markup)
    else:
        await message_or_callback.answer(text, reply_markup=markup)


@router.callback_query(F.data == "nav:access")
async def nav_access(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user or not await _ensure_public_for_callback(callback, bot, user):
        return
    await _send_access(callback, bot, user, lang)


@router.callback_query(F.data == "access:invite")
async def access_invite(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user:
        return await callback.answer("/start", show_alert=True)
    await _send_access(callback, bot, user, lang)


@router.message(Command("access"))
async def access_command(message: Message, bot: Bot) -> None:
    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    if not user or not await _ensure_public_for_message(message, bot, user):
        return
    await _send_access(message, bot, user, lang)


@router.message(F.refunded_payment)
async def refunded_payment(message: Message, bot: Bot) -> None:
    payment = message.refunded_payment
    if not payment:
        return
    result = await store.mark_payment_refunded(payment.telegram_payment_charge_id)
    if result.get("found"):
        current = await store.get_user(message.from_user.id)
        if not premium_is_active(current or {}):
            try:
                await remove_channel_access(bot, message.from_user.id)
            except Exception:
                logger.exception("Could not remove private access after refund")
        await store.update_user(message.from_user.id, sales_stage="engaged")
        await store.track_event(message.from_user.id, "payment_refunded", {"amount": payment.total_amount, "currency": payment.currency})


async def remove_channel_access(bot: Bot, user_id: int) -> None:
    channel_id = await _private_channel_id(bot)
    if not channel_id:
        raise RuntimeError("PRIVATE_CHANNEL_URL/ID is not resolvable")
    try:
        await bot.ban_chat_member(channel_id, user_id)
        await bot.unban_chat_member(channel_id, user_id, only_if_banned=True)
    finally:
        await store.update_user(user_id, channel_member=False)
        await store.track_event(user_id, "paid_channel_access_ended")


@router.callback_query(F.data == "subscription:manage")
async def subscription_manage(callback: CallbackQuery) -> None:
    user, lang = await _callback_user(callback)
    if not user or not user.get("subscription_recurring"):
        return await callback.answer(t(lang, "no_subscription"), show_alert=True)
    tier = _tier(user)
    until = str(user.get("premium_until") or "")[:10]
    renewal_enabled = not bool(user.get("subscription_canceled"))
    status = t(lang, "renewal_resumed", until=until) if renewal_enabled else t(lang, "renewal_canceled", until=until)
    await callback.answer()
    await _edit(callback, f"<b>{html.escape(product_title(lang, tier))}</b>\n{status}", keyboards.subscription_kb(lang, renewal_enabled, tier))


@router.callback_query(F.data == "subscription:cancel")
async def subscription_cancel(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    charge_id = (user or {}).get("subscription_charge_id")
    if not user or not charge_id or not user.get("subscription_recurring"):
        return await callback.answer(t(lang, "no_subscription"), show_alert=True)
    await bot.edit_user_star_subscription(callback.from_user.id, charge_id, is_canceled=True)
    await store.update_user(callback.from_user.id, subscription_canceled=True)
    await store.track_event(callback.from_user.id, "subscription_canceled", {"tier": _tier(user)})
    until = str(user.get("premium_until") or "")[:10]
    await callback.answer()
    await _edit(callback, t(lang, "renewal_canceled", until=until), keyboards.subscription_kb(lang, False, _tier(user)))


@router.callback_query(F.data == "subscription:resume")
async def subscription_resume(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    charge_id = (user or {}).get("subscription_charge_id")
    if not user or not charge_id or not user.get("subscription_recurring"):
        return await callback.answer(t(lang, "no_subscription"), show_alert=True)
    await bot.edit_user_star_subscription(callback.from_user.id, charge_id, is_canceled=False)
    await store.update_user(callback.from_user.id, subscription_canceled=False)
    await store.track_event(callback.from_user.id, "subscription_resumed", {"tier": _tier(user)})
    until = str(user.get("premium_until") or "")[:10]
    await callback.answer()
    await _edit(callback, t(lang, "renewal_resumed", until=until), keyboards.subscription_kb(lang, True, _tier(user)))


@router.callback_query(F.data == "call:request")
async def call_request_callback(callback: CallbackQuery, bot: Bot) -> None:
    user, lang = await _callback_user(callback)
    if not user or _tier(user) != "black":
        return await callback.answer(t(lang, "call_requires_plan"), show_alert=True)
    result = await store.request_call(callback.from_user.id)
    if not result.get("ok"):
        return await callback.answer(t(lang, "call_limit"), show_alert=True)
    await store.track_event(callback.from_user.id, "call_requested", {"request_id": result.get("id")})
    await callback.answer(t(lang, "call_requested"), show_alert=True)
    if settings.admin_id:
        await bot.send_message(
            settings.admin_id,
            f"📞 <b>Новая заявка на звонок</b>\nID заявки: <code>{result.get('id')}</code>\nЮзер: <code>{callback.from_user.id}</code>\nОтвет: <code>/send {callback.from_user.id} время</code>",
        )


@router.message(Command("call"))
async def call_request_command(message: Message, bot: Bot) -> None:
    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    if not user or _tier(user) != "black":
        return await message.answer(t(lang, "call_requires_plan"))
    result = await store.request_call(message.from_user.id)
    if not result.get("ok"):
        return await message.answer(t(lang, "call_limit"))
    await store.track_event(message.from_user.id, "call_requested", {"request_id": result.get("id")})
    await message.answer(t(lang, "call_requested"))
    if settings.admin_id:
        await bot.send_message(settings.admin_id, f"📞 Заявка <code>{result.get('id')}</code> · user <code>{message.from_user.id}</code>")


@router.message(Command("paysupport"))
async def payment_support(message: Message) -> None:
    user = await store.get_user(message.from_user.id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    await message.answer(t(lang, "payment_support"))


# ---------------------------- Admin -------------------------------------


async def _admin_home_text() -> str:
    try:
        stats = await store.stats()
        o = stats.get("overview", {})
        r = stats.get("revenue", {})
        fu = stats.get("followups", {})
        ch = stats.get("chat", {})
        return (
            "<b>💜 Victoria · админ-панель</b>\n\n"
            f"👥 Пользователи: <b>{o.get('users', 0)}</b> · доступны <b>{o.get('reachable', 0)}</b>\n"
            f"💬 Ждут ответа: <b>{ch.get('pending_replies', 0)}</b>\n"
            f"🧲 Дожимы в очереди: <b>{fu.get('pending', 0)}</b> · отправлено <b>{fu.get('sent', 0)}</b>\n"
            f"⭐ Stars: сегодня <b>{r.get('stars_1d', 0)}</b> · 7д <b>{r.get('stars_7d', 0)}</b> · lifetime <b>{r.get('lifetime_stars', 0)}</b>\n\n"
            "Быстрые действия — кнопками ниже.\n"
            "Для конкретного человека: <code>/user ID</code> · <code>/send ID текст</code>."
        )
    except Exception as exc:
        return (
            "<b>💜 Victoria · админ-панель</b>\n\n"
            f"⚠️ Не удалось загрузить сводку: <code>{html.escape(str(exc)[:700])}</code>\n\n"
            "Открой «Диагностика» ниже."
        )


def _stats_texts(stats: dict) -> tuple[str, str]:
    o = stats.get("overview", {})
    c = stats.get("channel", {})
    f = stats.get("funnel", {})
    f7 = stats.get("funnel_7d", {})
    r = stats.get("revenue", {})
    fu = stats.get("followups", {})
    ch = stats.get("chat", {})
    acq = stats.get("acquisition", {})
    first = (
        "<b>📊 Victoria · воронка</b>\n\n"
        f"👥 Всего: <b>{o.get('users', 0)}</b> · доступны: <b>{o.get('reachable', 0)}</b> · blocked: <b>{o.get('blocked', 0)}</b>\n"
        f"Новые: 24ч <b>{o.get('new_1d', 0)}</b> · 7д <b>{o.get('new_7d', 0)}</b> · 30д <b>{o.get('new_30d', 0)}</b>\n"
        f"Активные: 24ч <b>{o.get('active_1d', 0)}</b> · 7д <b>{o.get('active_7d', 0)}</b> · 30д <b>{o.get('active_30d', 0)}</b>\n\n"
        "<b>📣 Обязательный канал</b>\n"
        f"Gate: <b>{c.get('gate_shown', 0)}</b> · подписались: <b>{c.get('verified_users', 0)}</b> · <b>{c.get('verify_pct', 0)}%</b>\n"
        f"Подтверждены сейчас: <b>{c.get('members_now', 0)}</b> · failed checks: <b>{c.get('verify_failed_users', 0)}</b>\n\n"
        "<b>💰 Продажи</b>\n"
        f"Открыли приват: <b>{f.get('paywall_users', 0)}</b> · start→offer <b>{f.get('start_to_paywall_pct', 0)}%</b>\n"
        f"Нажали оплату: <b>{f.get('checkout_users', 0)}</b> · offer→checkout <b>{f.get('paywall_to_checkout_pct', 0)}%</b>\n"
        f"Плательщики: <b>{f.get('payer_users', 0)}</b> · checkout→paid <b>{f.get('checkout_to_paid_pct', 0)}%</b>\n"
        f"Start→paid: <b>{f.get('start_to_paid_pct', 0)}%</b> · premium сейчас: <b>{f.get('premium_active', 0)}</b>\n"
        f"🔥 Горячие checkout ≤24ч: <b>{f.get('hot_checkout_24h', 0)}</b>\n\n"
        "<b>🆕 Воронка новых за 7 дней</b>\n"
        f"Новые: <b>{f7.get('users', 0)}</b> · offer: <b>{f7.get('paywall_users', 0)}</b> · checkout: <b>{f7.get('checkout_users', 0)}</b> · paid: <b>{f7.get('payer_users', 0)}</b>\n"
        f"start→offer <b>{f7.get('start_to_paywall_pct', 0)}%</b> · offer→checkout <b>{f7.get('paywall_to_checkout_pct', 0)}%</b> · checkout→paid <b>{f7.get('checkout_to_paid_pct', 0)}%</b>"
    )
    second = (
        "<b>💵 Victoria · деньги / чат</b>\n\n"
        f"⭐ Сегодня: <b>{r.get('stars_1d', 0)}</b> · 7д: <b>{r.get('stars_7d', 0)}</b> · 30д: <b>{r.get('stars_30d', 0)}</b>\n"
        f"Lifetime: <b>{r.get('lifetime_stars', 0)} ⭐</b> · платежей <b>{r.get('payments', 0)}</b> · плательщиков <b>{r.get('payers', 0)}</b>\n"
        f"ARPPU: <b>{r.get('arppu_stars', 0)} ⭐</b> · возвраты: <b>{r.get('refunds', 0)}</b>\n"
        f"Тарифы: {_format_breakdown(r.get('tiers'))}\n"
        f"Stars по регионам: {_format_breakdown(r.get('markets'))}\n\n"
        "<b>🧲 Дожимы</b>\n"
        f"В очереди: <b>{fu.get('pending', 0)}</b> · отправлено: <b>{fu.get('sent', 0)}</b>\n"
        f"Оплат после дожима: <b>{fu.get('conversions', 0)}</b> · <b>{fu.get('conversion_pct', 0)}%</b>\n"
        f"7д: отправлено <b>{fu.get('sent_7d', 0)}</b> · оплат после них <b>{fu.get('conversions_7d', 0)}</b>\n"
        f"По типам 7д: {_format_breakdown(fu.get('by_type_7d'))}\n\n"
        f"💬 Ждут ответа: <b>{ch.get('pending_replies', 0)}</b> · написали хотя бы раз: <b>{ch.get('chatters', 0)}</b> · всего входящих: <b>{ch.get('user_messages', 0)}</b>\n"
        f"Языки: {_format_breakdown(acq.get('languages'))}\n"
        f"Регионы: {_format_breakdown(acq.get('markets'))}\n"
        f"Источники: {_format_breakdown(acq.get('refs'))}\n"
        f"Регионы 7д: {_format_breakdown(acq.get('markets_7d'))}\n"
        f"Источники 7д: {_format_breakdown(acq.get('refs_7d'))}"
    )
    return first, second


async def _diag_text(bot: Bot) -> str:
    lines = [
        "<b>🩺 Victoria · диагностика</b>",
        f"FOLLOWUPS_ENABLED: <b>{settings.followups_enabled}</b>",
        "CHAT: <b>manual</b>",
        f"SUPABASE key: <b>{html.escape(settings.supabase_key_kind)}</b>",
        f"ADMIN_ID: <code>{settings.admin_id}</code>",
    ]
    try:
        check = await store.operational_check()
        lines.append(f"DB queue/RPC: <b>OK</b> · pending={int(check.get('pending_jobs', 0))}")
    except Exception as exc:
        lines.append(f"DB queue/RPC: <b>ERROR</b> · <code>{html.escape(str(exc)[:700])}</code>")
    for lang in sorted(LANGS):
        ref = settings.public_channel_ref(lang)
        caps = await channel_capabilities(bot, ref)
        state = "✅ invite" if caps.can_invite else "❌ no-invite"
        lines.append(
            f"PUB {lang}: <code>{html.escape(str(ref or 'UNRESOLVED'))}</code> · {state}"
        )
    private_caps = await channel_capabilities(bot, settings.private_channel_ref)
    private_state = (
        ("✅ invite" if private_caps.can_invite else "❌ no-invite")
        + " / "
        + ("✅ restrict" if private_caps.can_restrict else "⚠️ no-restrict")
    )
    lines.append(
        f"PRIVATE: <code>{html.escape(str(settings.private_channel_ref or 'UNRESOLVED'))}</code> · {private_state}"
    )
    try:
        me = await bot.get_me()
        lines.append(f"Telegram bot: <b>OK</b> @{html.escape(me.username or '')}")
    except Exception as exc:
        lines.append(f"Telegram bot: <b>ERROR</b> · <code>{html.escape(str(exc)[:300])}</code>")
    return "\n".join(lines)[:4000]


async def _jobs_text(user_id: int | None = None) -> str:
    try:
        rows = await store.recent_jobs(user_id, 30)
    except Exception as exc:
        return f"Queue error: <code>{html.escape(str(exc)[:1000])}</code>"
    if not rows:
        return "<b>🧲 Дожимы</b>\n\nОчередь пуста."
    lines = [f"<b>🧲 Дожимы · последние {len(rows)}</b>"]
    for row in rows:
        err = compact_text(str(row.get("last_error") or ""), 70)
        attempts = int(row.get("attempts") or 0)
        line = (
            f"#{row.get('id')} · <code>{row.get('user_id')}</code> · "
            f"<b>{html.escape(str(row.get('job_type')))}</b> · {html.escape(str(row.get('status')))} · "
            f"{str(row.get('scheduled_at') or '')[:16]} · try {attempts}"
        )
        if err:
            line += f" · ⚠️ {html.escape(err)}"
        lines.append(line)
    return "\n".join(lines)[:4000]


async def _queue_text() -> str:
    rows = await store.reply_queue()
    if not rows:
        return "<b>💬 Очередь ответов</b>\n\nНикто не ждёт ответа."
    lines = [f"<b>💬 Ждут ответа · {len(rows)}</b>"]
    enriched = [(row, await store.get_user(int(row["user_id"]))) for row in rows]
    ranks = {"black": 0, "ultra": 0, "pro": 1, "plus": 2, "free": 3}
    enriched.sort(key=lambda item: (ranks.get(_tier(item[1]), 3), item[0].get("updated_at", "")))
    for row, user in enriched[:50]:
        last = await store.last_message(int(row["user_id"]), "user")
        preview = compact_text(str((last or {}).get("content") or ""), 70)
        lines.append(
            f"{_tier(user)} · <code>{row['user_id']}</code> · {html.escape(str((user or {}).get('first_name') or ''))} · {html.escape(preview)}"
        )
    return "\n".join(lines)[:4000]


async def _calls_text() -> str:
    calls = await store.pending_calls()
    if not calls:
        return "<b>📞 Звонки</b>\n\nЗаявок нет."
    lines = ["<b>📞 Заявки на звонок</b>"]
    for c in calls:
        user = await store.get_user(int(c["user_id"]))
        lines.append(f"#{c['id']} · <code>{c['user_id']}</code> · {html.escape(str((user or {}).get('first_name') or ''))} · {str(c['created_at'])[:16]}")
    return "\n".join(lines)[:4000]


def _pct(value: object) -> str:
    try:
        num = float(value or 0)
    except (TypeError, ValueError):
        num = 0.0
    return f"{num:.2f}".rstrip("0").rstrip(".")


def _partner_link(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={partner_ref(code)}"


def _partner_dashboard_text(partner: dict, stats: dict, bot_username: str, *, admin_view: bool = False) -> str:
    traffic = stats.get("traffic", {}) if isinstance(stats, dict) else {}
    funnel = stats.get("funnel", {}) if isinstance(stats, dict) else {}
    revenue = stats.get("revenue", {}) if isinstance(stats, dict) else {}
    recent = stats.get("recent", {}) if isinstance(stats, dict) else {}
    code = str(partner.get("code") or "")
    status = "🟢 активен" if partner.get("active") else "⏸ пауза"
    lines = [
        "<b>🚦 Victoria · профиль заливщика</b>",
        "",
        f"👤 <b>{html.escape(str(partner.get('display_name') or code))}</b> · {status}",
        f"🏷 Код: <code>{html.escape(code)}</code>",
        f"💸 Комиссия: <b>{_pct(partner.get('commission_pct'))}%</b> от подтверждённых Stars-платежей",
        f"🔗 Ссылка: <code>{html.escape(_partner_link(bot_username, code))}</code>",
    ]
    if admin_view:
        lines.append(f"Telegram ID: <code>{partner.get('telegram_user_id')}</code>")
    lines += [
        "",
        "<b>👥 Трафик</b>",
        f"Стартов по ссылке: <b>{traffic.get('link_starts', 0)}</b> · уникальных: <b>{traffic.get('unique_link_starters', 0)}</b> · за 7д: <b>{traffic.get('link_starts_7d', 0)}</b>",
        f"Новых закреплённых лидов: сегодня <b>{traffic.get('leads_1d', 0)}</b> · 7д <b>{traffic.get('leads_7d', 0)}</b> · 30д <b>{traffic.get('leads_30d', 0)}</b>",
        f"Всего закреплено: <b>{traffic.get('leads', 0)}</b> · доступны: <b>{traffic.get('reachable', 0)}</b> · blocked: <b>{traffic.get('blocked', 0)}</b>",
        f"Активны 7д: <b>{traffic.get('active_7d', 0)}</b>",
        "",
        "<b>📈 Воронка</b>",
        f"Канал подтверждён: <b>{funnel.get('gate_verified', 0)}</b>",
        f"Открыли тарифы: <b>{funnel.get('paywall_users', 0)}</b> · checkout: <b>{funnel.get('checkout_users', 0)}</b> · плательщики: <b>{funnel.get('payer_users', 0)}</b>",
        f"offer→checkout: <b>{funnel.get('paywall_to_checkout_pct', 0)}%</b> · lead→paid: <b>{funnel.get('lead_to_paid_pct', 0)}%</b>",
        f"За 7д: offer <b>{recent.get('paywall_7d', 0)}</b> · checkout <b>{recent.get('checkout_7d', 0)}</b> · paid <b>{recent.get('payers_7d', 0)}</b>",
        "",
        "<b>⭐ Деньги</b>",
        f"Выручка с трафика: <b>{revenue.get('gross_stars', 0)} ⭐</b> · за 7д: <b>{revenue.get('gross_stars_7d', 0)} ⭐</b>",
        f"Начислено комиссии: <b>{revenue.get('commission_earned_stars', 0)} ⭐</b> · за 7д: <b>{revenue.get('commission_earned_7d_stars', 0)} ⭐</b>",
        f"Уже отмечено выплаченным: <b>{revenue.get('paid_out_stars', 0)} ⭐</b>",
        f"К выплате: <b>{revenue.get('balance_stars', 0)} ⭐</b>",
        "",
        "Комиссия считается только с реальных успешных платежей без возврата. Изменение процента влияет только на будущие продажи.",
    ]
    return "\n".join(lines)[:4000]


async def _partners_admin_text() -> str:
    partners = await store.list_partners()
    if not partners:
        return (
            "<b>🚦 Заливщики трафика</b>\n\nПока никого нет.\n\n"
            "Добавить: <code>/partneradd TELEGRAM_ID CODE PERCENT NAME</code>\n"
            "Пример: <code>/partneradd 123456789 max_de 30 Max DE</code>"
        )
    shown = partners[:30]
    raw_stats = await asyncio.gather(
        *(store.partner_stats(str(p.get("code"))) for p in shown),
        return_exceptions=True,
    )
    active = sum(1 for p in partners if p.get("active"))
    lines = [f"<b>🚦 Заливщики · {len(partners)}</b> · активны {active}", ""]
    total_leads = total_gross = total_earned = total_balance = 0
    for p, st in zip(shown, raw_stats):
        icon = "🟢" if p.get("active") else "⏸"
        if isinstance(st, Exception):
            lines.append(
                f"{icon} <b>{html.escape(str(p.get('display_name') or p.get('code')))}</b> · "
                f"<code>{html.escape(str(p.get('code')))}</code> · {_pct(p.get('commission_pct'))}% · ⚠️ stats"
            )
            continue
        tr = (st or {}).get("traffic") or {}
        rev = (st or {}).get("revenue") or {}
        leads = int(tr.get("leads") or 0)
        gross = int(rev.get("gross_stars") or 0)
        earned = int(rev.get("commission_earned_stars") or 0)
        balance = int(rev.get("balance_stars") or 0)
        total_leads += leads
        total_gross += gross
        total_earned += earned
        total_balance += balance
        lines.append(
            f"{icon} <b>{html.escape(str(p.get('display_name') or p.get('code')))}</b> · "
            f"<code>{html.escape(str(p.get('code')))}</code> · {_pct(p.get('commission_pct'))}%\n"
            f"└ лиды <b>{leads}</b> · выручка <b>{gross}⭐</b> · начислено <b>{earned}⭐</b> · к выплате <b>{balance}⭐</b>"
        )
    lines += [
        "",
        f"<b>Итого показанных:</b> лиды {total_leads} · выручка {total_gross}⭐ · начислено {total_earned}⭐ · к выплате {total_balance}⭐",
        "",
        "Профиль: <code>/partnerinfo CODE</code>",
        "Добавить: <code>/partneradd ID CODE PERCENT NAME</code>",
        "Процент: <code>/partnerrate CODE PERCENT</code>",
        "Пауза: <code>/partnerpause CODE</code> · вернуть: <code>/partnerresume CODE</code>",
        "Отметить выплату: <code>/partnerpay CODE STARS комментарий</code>",
    ]
    if len(partners) > len(shown):
        lines.append(f"Показаны первые {len(shown)} из {len(partners)}.")
    return "\n".join(lines)[:4000]


async def _show_partner_self(message: Message, bot: Bot) -> None:
    partner = await store.get_partner_by_telegram_id(message.from_user.id)
    if not partner:
        await message.answer("У тебя пока нет профиля заливщика Victoria.")
        return
    stats = await store.partner_stats(str(partner.get("code")))
    me = await bot.get_me()
    await message.answer(
        _partner_dashboard_text(partner, stats, me.username or "vika_backstagebot"),
        reply_markup=keyboards.partner_profile_kb(),
    )


@router.message(Command("partner"))
async def partner_self(message: Message, bot: Bot) -> None:
    await _show_partner_self(message, bot)


@router.callback_query(F.data == "partner:self")
async def partner_self_refresh(callback: CallbackQuery, bot: Bot) -> None:
    partner = await store.get_partner_by_telegram_id(callback.from_user.id)
    if not partner:
        return await callback.answer("Профиль заливщика не найден", show_alert=True)
    stats = await store.partner_stats(str(partner.get("code")))
    me = await bot.get_me()
    text = _partner_dashboard_text(partner, stats, me.username or "vika_backstagebot")
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=keyboards.partner_profile_kb())
        except TelegramBadRequest:
            pass
    await callback.answer("Обновлено")


@router.message(Command("partners"), F.from_user.id == settings.admin_id)
async def admin_partners(message: Message) -> None:
    await message.answer(await _partners_admin_text(), reply_markup=keyboards.admin_back_kb())


@router.message(Command("partneradd"), F.from_user.id == settings.admin_id)
async def admin_partner_add(message: Message, command: CommandObject, bot: Bot) -> None:
    parts = (command.args or "").split(maxsplit=3)
    if len(parts) < 3 or not parts[0].isdigit():
        await message.answer("Формат: <code>/partneradd TELEGRAM_ID CODE PERCENT NAME</code>")
        return
    try:
        telegram_id = int(parts[0])
        code = normalize_partner_code(parts[1])
        pct = float(parts[2].replace(",", "."))
        if pct < 0 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("Проверь ID, code (a-z/0-9/_) и процент 0–100.")
        return
    name = compact_text(parts[3] if len(parts) > 3 else code, 120)
    try:
        partner = await store.create_partner(telegram_id, code, name, pct)
    except Exception as exc:
        await message.answer(f"Не удалось создать профиль: <code>{html.escape(str(exc)[:700])}</code>")
        return
    me = await bot.get_me()
    link = _partner_link(me.username or "vika_backstagebot", code)
    notified = True
    try:
        await bot.send_message(
            telegram_id,
            "🚦 <b>Тебе открыт профиль заливщика Victoria</b>\n\n"
            f"Твоя ссылка: <code>{html.escape(link)}</code>\n"
            f"Комиссия: <b>{_pct(pct)}%</b>\n\n"
            "Статистика и начисления: /partner",
        )
    except Exception:
        notified = False
    await message.answer(
        f"✅ Создан <b>{html.escape(str(partner.get('display_name')))}</b> · <code>{code}</code> · {_pct(pct)}%\n"
        f"Ссылка: <code>{html.escape(link)}</code>\n"
        + ("Профиль отправлен заливщику." if notified else "⚠️ Не смог написать ему первым — пусть один раз откроет бота /start, затем /partner."),
    )


@router.message(Command("partnerinfo"), F.from_user.id == settings.admin_id)
async def admin_partner_info(message: Message, command: CommandObject, bot: Bot) -> None:
    raw = compact_text(command.args or "", 64)
    try:
        code = normalize_partner_code(raw)
    except ValueError:
        await message.answer("Формат: <code>/partnerinfo CODE</code>")
        return
    partner = await store.get_partner_by_code(code)
    if not partner:
        await message.answer("Заливщик не найден.")
        return
    stats = await store.partner_stats(code)
    me = await bot.get_me()
    await message.answer(
        _partner_dashboard_text(partner, stats, me.username or "vika_backstagebot", admin_view=True),
        reply_markup=keyboards.admin_back_kb(),
    )


@router.message(Command("partnerrate"), F.from_user.id == settings.admin_id)
async def admin_partner_rate(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").split()
    if len(parts) != 2:
        await message.answer("Формат: <code>/partnerrate CODE PERCENT</code>")
        return
    try:
        code = normalize_partner_code(parts[0])
        pct = float(parts[1].replace(",", "."))
        if pct < 0 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("Некорректный code или процент 0–100.")
        return
    await store.update_partner(code, commission_pct=pct)
    await message.answer(f"✅ {code}: новая комиссия <b>{_pct(pct)}%</b>. Старые начисления не пересчитываются.")


@router.message(Command("partnerpause"), F.from_user.id == settings.admin_id)
async def admin_partner_pause(message: Message, command: CommandObject) -> None:
    try:
        code = normalize_partner_code(command.args or "")
        await store.update_partner(code, active=False)
    except (ValueError, DatabaseError):
        await message.answer("Формат: <code>/partnerpause CODE</code>")
        return
    await message.answer(f"⏸ {code} на паузе. Новые регистрации по его ссылке больше не атрибутируются.")


@router.message(Command("partnerresume"), F.from_user.id == settings.admin_id)
async def admin_partner_resume(message: Message, command: CommandObject) -> None:
    try:
        code = normalize_partner_code(command.args or "")
        await store.update_partner(code, active=True)
    except (ValueError, DatabaseError):
        await message.answer("Формат: <code>/partnerresume CODE</code>")
        return
    await message.answer(f"🟢 {code} снова активен.")


@router.message(Command("partnerpay"), F.from_user.id == settings.admin_id)
async def admin_partner_pay(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Формат: <code>/partnerpay CODE STARS комментарий</code>")
        return
    try:
        code = normalize_partner_code(parts[0])
        amount = int(parts[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Некорректный code или сумма Stars.")
        return
    partner = await store.get_partner_by_code(code)
    if not partner:
        await message.answer("Заливщик не найден.")
        return
    stats = await store.partner_stats(code)
    balance = int((stats.get("revenue") or {}).get("balance_stars") or 0)
    if amount > balance:
        await message.answer(f"Сейчас к выплате только <b>{balance} ⭐</b>. Сумма не записана.")
        return
    note = compact_text(parts[2] if len(parts) > 2 else "", 500)
    await store.record_partner_payout(int(partner["id"]), amount, note)
    fresh = await store.partner_stats(code)
    new_balance = int((fresh.get("revenue") or {}).get("balance_stars") or 0)
    await message.answer(f"✅ Выплата <b>{amount} ⭐</b> отмечена для {html.escape(str(partner.get('display_name')))}. Остаток: <b>{new_balance} ⭐</b>.")


@router.message(Command("admin"), F.from_user.id == settings.admin_id)
async def admin_help(message: Message) -> None:
    await message.answer(await _admin_home_text(), reply_markup=keyboards.admin_panel_kb())


@router.callback_query(F.data.startswith("ap:"), F.from_user.id == settings.admin_id)
async def admin_panel_callback(callback: CallbackQuery, bot: Bot) -> None:
    action = (callback.data or "ap:home").split(":", 1)[1]
    try:
        if action == "home":
            text = await _admin_home_text()
            kb = keyboards.admin_panel_kb()
        elif action == "stats":
            stats = await store.stats()
            first, second = _stats_texts(stats)
            text = first + "\n\n" + second
            kb = keyboards.admin_back_kb()
        elif action == "queue":
            text = await _queue_text()
            kb = keyboards.admin_back_kb()
        elif action == "jobs":
            text = await _jobs_text()
            kb = keyboards.admin_back_kb()
        elif action == "calls":
            text = await _calls_text()
            kb = keyboards.admin_back_kb()
        elif action == "diag":
            text = await _diag_text(bot)
            kb = keyboards.admin_back_kb()
        elif action == "broadcast":
            text = (
                "<b>📣 Рассылка</b>\n\n"
                "Формат: <code>/broadcast SEGMENT текст</code>\n"
                "Сегменты: <code>all free paid ua cis eu us latam asia global uk ru en de fr es</code>\n\n"
                "Пример: <code>/broadcast ru Новий пост уже в канале 👀</code>"
            )
            kb = keyboards.admin_back_kb()
        elif action == "partners":
            text = await _partners_admin_text()
            kb = keyboards.admin_back_kb()
        elif action == "userhelp":
            text = (
                "<b>👤 Карточка пользователя</b>\n\n"
                "Открыть: <code>/user USER_ID</code>\n"
                "История: <code>/history USER_ID</code>\n"
                "Написать: <code>/send USER_ID текст</code>\n"
                "Язык: <code>/setlang USER_ID uk|ru|en|de|fr|es</code>\n"
                "Регион: <code>/setregion USER_ID ua|cis|eu|us|latam|asia|global</code>\n"
                "Дожимы: <code>/followups USER_ID on|off</code>"
            )
            kb = keyboards.admin_back_kb()
        else:
            text = await _admin_home_text()
            kb = keyboards.admin_panel_kb()
        if callback.message:
            try:
                await callback.message.edit_text(text[:4000], reply_markup=kb)
            except TelegramBadRequest:
                await callback.message.answer(text[:4000], reply_markup=kb)
        await callback.answer()
    except Exception as exc:
        logger.exception("Admin panel action failed: %s", action)
        await callback.answer("Ошибка. Проверь /diag", show_alert=True)


@router.message(Command("setregion"), F.from_user.id == settings.admin_id)
async def admin_set_region(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").lower().split()
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in MARKETS:
        return await message.answer("Usage: /setregion USER_ID ua|cis|latam|asia|eu|us|global")
    target, market = int(parts[0]), parts[1]
    if not await store.get_user(target):
        return await message.answer("User not found.")
    await store.set_region(target, market)
    await store.track_event(target, "admin_region_changed", {"market": market})
    await message.answer(f"Region for <code>{target}</code>: <b>{market}</b>")


@router.message(Command("setlang"), F.from_user.id == settings.admin_id)
async def admin_set_language(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").lower().split()
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in LANGS:
        return await message.answer("Usage: /setlang USER_ID uk|ru|en|de|fr|es")
    target, lang = int(parts[0]), parts[1]
    if not await store.get_user(target):
        return await message.answer("User not found.")
    await store.set_language(target, lang)
    await store.cancel_jobs(target, ["gate_6h"])
    await store.track_event(target, "admin_language_changed", {"lang": lang})
    await message.answer(f"Language for <code>{target}</code>: <b>{lang}</b>. Public-channel check reset.")


@router.message(Command("followups"), F.from_user.id == settings.admin_id)
async def admin_followups(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").lower().split()
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in {"on", "off"}:
        return await message.answer("Usage: /followups USER_ID on|off")
    user_id = int(parts[0])
    user = await store.get_user(user_id)
    if not user:
        return await message.answer("User not found.")
    paused = parts[1] == "off"
    await store.update_user(user_id, automation_paused=paused)
    if paused:
        await store.cancel_jobs(user_id)
    await message.answer(f"Follow-ups for <code>{user_id}</code>: <b>{'OFF' if paused else 'ON'}</b>")


@router.message(Command("note"), F.from_user.id == settings.admin_id)
async def admin_note(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    raw_id, sep, body = raw.partition(" ")
    if not raw_id.isdigit() or not sep:
        return await message.answer("Usage: /note USER_ID text")
    if not await store.get_user(int(raw_id)):
        return await message.answer("User not found.")
    await store.update_user(int(raw_id), admin_notes=compact_text(body, 1000))
    await message.answer("Заметка сохранена.")


@router.message(Command("user"), F.from_user.id == settings.admin_id)
async def admin_user_card(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit():
        return await message.answer("Usage: /user USER_ID")
    user = await store.get_user(int(raw))
    if not user:
        return await message.answer("User not found.")
    last = await store.last_message(int(raw), "user")
    last_preview = html.escape(compact_text(str((last or {}).get("content") or "—"), 180))
    await message.answer(
        f"<b>{html.escape(str(user.get('first_name') or 'User'))}</b> · @{html.escape(str(user.get('username') or '—'))}\n"
        f"ID: <code>{raw}</code>\n"
        f"Lang: <b>{html.escape(str(user.get('lang') or '—'))}</b> · Region: <b>{html.escape(str(user.get('market') or '—'))}</b> · Ref: <b>{html.escape(str(user.get('ref') or 'direct'))}</b>\n"
        f"Public: <b>{'yes' if user.get('public_channel_member') else 'no'}</b> · Private: <b>{'yes' if user.get('channel_member') else 'no'}</b>\n"
        f"Plan: <b>{html.escape(_tier(user))}</b> · Stage: <code>{html.escape(str(user.get('sales_stage') or '—'))}</code>\n"
        f"Messages: <b>{user.get('total_messages', 0)}</b> · Blocked: <b>{'yes' if user.get('blocked') else 'no'}</b>\n"
        f"Follow-ups: <b>{'OFF' if user.get('automation_paused') else 'ON'}</b>\n"
        f"Note: {html.escape(str(user.get('admin_notes') or '—'))}\n\n"
        f"Last: {last_preview}",
        reply_markup=keyboards.admin_ticket_kb(int(raw)),
    )


@router.message(Command("history"), F.from_user.id == settings.admin_id)
async def admin_history(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit():
        return await message.answer("Usage: /history USER_ID")
    rows = await store.recent_messages(int(raw), 20)
    if not rows:
        return await message.answer("Истории нет.")
    parts = [f"<b>Последние сообщения · {raw}</b>"]
    for row in rows:
        icon = "👤" if row.get("role") == "user" else "💜"
        parts.append(f"{icon} {html.escape(compact_text(str(row.get('content') or ''), 500))}")
    text = "\n\n".join(parts)
    await message.answer(text[:4000])


@router.message(Command("stats"), F.from_user.id == settings.admin_id)
@router.message(Command("funnel"), F.from_user.id == settings.admin_id)
async def admin_stats(message: Message) -> None:
    stats = await store.stats()
    o = stats.get("overview", {})
    c = stats.get("channel", {})
    f = stats.get("funnel", {})
    r = stats.get("revenue", {})
    fu = stats.get("followups", {})
    ch = stats.get("chat", {})
    acq = stats.get("acquisition", {})
    await message.answer(
        "<b>Victoria · воронка</b>\n\n"
        f"👥 Всего: <b>{o.get('users', 0)}</b> · доступны: <b>{o.get('reachable', 0)}</b> · blocked: <b>{o.get('blocked', 0)}</b>\n"
        f"Новые: 24ч <b>{o.get('new_1d', 0)}</b> · 7д <b>{o.get('new_7d', 0)}</b> · 30д <b>{o.get('new_30d', 0)}</b>\n"
        f"Активные: 24ч <b>{o.get('active_1d', 0)}</b> · 7д <b>{o.get('active_7d', 0)}</b> · 30д <b>{o.get('active_30d', 0)}</b>\n\n"
        "<b>📣 Обязательный канал</b>\n"
        f"Gate: <b>{c.get('gate_shown', 0)}</b> · подписались: <b>{c.get('verified_users', 0)}</b> · <b>{c.get('verify_pct', 0)}%</b>\n"
        f"Подтверждены сейчас: <b>{c.get('members_now', 0)}</b> · failed checks: <b>{c.get('verify_failed_users', 0)}</b>\n\n"
        "<b>💰 Продажи</b>\n"
        f"Открыли приват: <b>{f.get('paywall_users', 0)}</b> · start→offer <b>{f.get('start_to_paywall_pct', 0)}%</b>\n"
        f"Нажали оплату: <b>{f.get('checkout_users', 0)}</b> · offer→checkout <b>{f.get('paywall_to_checkout_pct', 0)}%</b>\n"
        f"Плательщики: <b>{f.get('payer_users', 0)}</b> · checkout→paid <b>{f.get('checkout_to_paid_pct', 0)}%</b>\n"
        f"Start→paid: <b>{f.get('start_to_paid_pct', 0)}%</b> · premium сейчас: <b>{f.get('premium_active', 0)}</b>"
    )
    await message.answer(
        "<b>Victoria · деньги / чат</b>\n\n"
        f"⭐ Сегодня: <b>{r.get('stars_1d', 0)}</b> · 7д: <b>{r.get('stars_7d', 0)}</b> · 30д: <b>{r.get('stars_30d', 0)}</b>\n"
        f"Lifetime: <b>{r.get('lifetime_stars', 0)} ⭐</b> · платежей <b>{r.get('payments', 0)}</b> · плательщиков <b>{r.get('payers', 0)}</b>\n"
        f"ARPPU: <b>{r.get('arppu_stars', 0)} ⭐</b> · возвраты: <b>{r.get('refunds', 0)}</b>\n"
        f"Тарифы: {_format_breakdown(r.get('tiers'))}\n"
        f"Stars по регионам: {_format_breakdown(r.get('markets'))}\n\n"
        "<b>🧲 Дожимы</b>\n"
        f"В очереди: <b>{fu.get('pending', 0)}</b> · отправлено: <b>{fu.get('sent', 0)}</b>\n"
        f"Оплат после дожима: <b>{fu.get('conversions', 0)}</b> · <b>{fu.get('conversion_pct', 0)}%</b>\n"
        f"По типам: {_format_breakdown(fu.get('by_type'))}\n\n"
        f"💬 Ждут ответа: <b>{ch.get('pending_replies', 0)}</b> · написали хотя бы раз: <b>{ch.get('chatters', 0)}</b> · всего входящих: <b>{ch.get('user_messages', 0)}</b>\n"
        f"Языки: {_format_breakdown(acq.get('languages'))}\n"
        f"Регионы: {_format_breakdown(acq.get('markets'))}\n"
        f"Источники: {_format_breakdown(acq.get('refs'))}"
    )


@router.message(Command("diag"), F.from_user.id == settings.admin_id)
async def admin_diag(message: Message, bot: Bot) -> None:
    lines = [
        "<b>Victoria diagnostics</b>",
        f"FOLLOWUPS_ENABLED: <b>{settings.followups_enabled}</b>",
        "CHAT: <b>manual</b>",
        f"SUPABASE key: <b>{html.escape(settings.supabase_key_kind)}</b>",
        f"ADMIN_ID: <code>{settings.admin_id}</code>",
    ]
    try:
        check = await store.operational_check()
        lines.append(f"DB queue/RPC: <b>OK</b> · pending={int(check.get('pending_jobs', 0))}")
    except Exception as exc:
        lines.append(f"DB queue/RPC: <b>ERROR</b> · <code>{html.escape(str(exc)[:700])}</code>")
    for lang in sorted(LANGS):
        ref = settings.public_channel_ref(lang)
        caps = await channel_capabilities(bot, ref)
        state = "✅ invite" if caps.can_invite else "❌ no-invite"
        lines.append(
            f"PUB {lang}: <code>{html.escape(str(ref or 'UNRESOLVED'))}</code> · {state}"
        )
    private_caps = await channel_capabilities(bot, settings.private_channel_ref)
    private_state = (
        ("✅ invite" if private_caps.can_invite else "❌ no-invite")
        + " / "
        + ("✅ restrict" if private_caps.can_restrict else "⚠️ no-restrict")
    )
    lines.append(
        f"PRIVATE: <code>{html.escape(str(settings.private_channel_ref or 'UNRESOLVED'))}</code> · {private_state}"
    )
    try:
        me = await bot.get_me()
        lines.append(f"Telegram bot: <b>OK</b> @{html.escape(me.username or '')}")
    except Exception as exc:
        lines.append(f"Telegram bot: <b>ERROR</b> · <code>{html.escape(str(exc)[:300])}</code>")
    await message.answer("\n".join(lines)[:4000])


@router.message(Command("jobs"), F.from_user.id == settings.admin_id)
async def admin_jobs(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    user_id = int(raw) if raw.isdigit() else None
    try:
        rows = await store.recent_jobs(user_id, 30)
    except Exception as exc:
        return await message.answer(f"Queue error: <code>{html.escape(str(exc)[:1000])}</code>")
    if not rows:
        return await message.answer("Automation jobs: пусто.")
    lines = [f"<b>Automation jobs · {len(rows)}</b>"]
    for row in rows:
        err = compact_text(str(row.get("last_error") or ""), 80)
        line = (
            f"#{row.get('id')} · <code>{row.get('user_id')}</code> · "
            f"<b>{html.escape(str(row.get('job_type')))}</b> · {html.escape(str(row.get('status')))} · "
            f"{str(row.get('scheduled_at') or '')[:16]}"
        )
        if err:
            line += f" · ⚠️ {html.escape(err)}"
        lines.append(line)
    await message.answer("\n".join(lines)[:4000])


@router.message(Command("queue"), F.from_user.id == settings.admin_id)
async def admin_reply_queue(message: Message) -> None:
    rows = await store.reply_queue()
    if not rows:
        return await message.answer("Никто не ждёт ответа.")
    lines = [f"<b>Ждут ответа · {len(rows)}</b>"]
    enriched = [(row, await store.get_user(int(row["user_id"]))) for row in rows]
    ranks = {"black": 0, "ultra": 0, "pro": 1, "plus": 2, "free": 3}
    enriched.sort(key=lambda item: (ranks.get(_tier(item[1]), 3), item[0].get("updated_at", "")))
    for row, user in enriched[:50]:
        last = await store.last_message(int(row["user_id"]), "user")
        preview = compact_text(str((last or {}).get("content") or ""), 70)
        lines.append(
            f"{_tier(user)} · <code>{row['user_id']}</code> · {html.escape(str((user or {}).get('first_name') or ''))} · {html.escape(preview)}"
        )
    await message.answer("\n".join(lines)[:4000])


@router.message(Command("calls"), F.from_user.id == settings.admin_id)
async def admin_calls(message: Message) -> None:
    calls = await store.pending_calls()
    if not calls:
        return await message.answer("Заявок на звонок нет.")
    lines = ["<b>Заявки на звонок</b>"]
    for c in calls:
        user = await store.get_user(int(c["user_id"]))
        lines.append(f"#{c['id']} · <code>{c['user_id']}</code> · {html.escape(str((user or {}).get('first_name') or ''))} · {str(c['created_at'])[:16]}")
    await message.answer("\n".join(lines))


@router.message(Command("call_done"), F.from_user.id == settings.admin_id)
async def admin_call_done(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit():
        return await message.answer("Usage: /call_done REQUEST_ID")
    await message.answer("Готово." if await store.complete_call(int(raw)) else "Заявка не найдена.")


@router.message(Command("call_cancel"), F.from_user.id == settings.admin_id)
async def admin_call_cancel(message: Message, command: CommandObject) -> None:
    raw = (command.args or "").strip()
    if not raw.isdigit():
        return await message.answer("Usage: /call_cancel REQUEST_ID")
    await message.answer("Отменено." if await store.cancel_call(int(raw)) else "Заявка не найдена.")


async def _after_admin_reply(user_id: int, body: str, event: str) -> str:
    # Telegram delivery is the important action. Database bookkeeping is best-effort
    # so a temporary Supabase error cannot turn a delivered message into a failed reply.
    errors: list[str] = []
    operations = [
        ("message_log", store.add_message(user_id, "assistant", compact_text(body, 4000))),
        ("clear_queue", store.clear_pending_reply(user_id)),
        ("cancel_followups", store.cancel_jobs(user_id, OFFER_JOB_TYPES + CHECKOUT_JOB_TYPES)),
        ("user_update", store.update_user(user_id, last_admin_reply_at=datetime.now(timezone.utc).isoformat())),
        ("event", store.track_event(user_id, event)),
    ]
    for label, operation in operations:
        try:
            await operation
        except Exception as exc:
            logger.exception("Post-admin-reply bookkeeping failed: %s user=%s", label, user_id)
            errors.append(label)
    suffix = f" · DB warning: {', '.join(errors)}" if errors else ""
    return f"✅ Доставлено пользователю {user_id}{suffix}"


async def _send_admin_text(bot: Bot, user_id: int, body: str, event: str) -> str:
    if not await store.get_user(user_id):
        return "User not found."
    try:
        await bot.send_message(user_id, body, parse_mode=None)
        return await _after_admin_reply(user_id, body, event)
    except TelegramForbiddenError:
        await store.mark_blocked(user_id)
        return "Пользователь заблокировал бота."
    except TelegramBadRequest as exc:
        return f"Telegram error: {exc}"


@router.message(Command("send"), F.from_user.id == settings.admin_id)
@router.message(Command("msg"), F.from_user.id == settings.admin_id)
async def admin_send_to_user(message: Message, command: CommandObject, bot: Bot) -> None:
    raw = (command.args or "").strip()
    raw_id, sep, body = raw.partition(" ")
    if not raw_id.isdigit() or not sep or not body.strip():
        return await message.answer("Usage: /send USER_ID text")
    result = await _send_admin_text(bot, int(raw_id), compact_text(body, 4000), "admin_direct_message")
    await message.answer(html.escape(result))


@router.callback_query(F.data.startswith("aq:"), F.from_user.id == settings.admin_id)
async def admin_quick_reply(callback: CallbackQuery, bot: Bot) -> None:
    try:
        _, raw_id, kind = callback.data.split(":", 2)
        user_id = int(raw_id)
    except (ValueError, AttributeError):
        return await callback.answer("Bad action", show_alert=True)
    user = await store.get_user(user_id)
    if not user:
        return await callback.answer("User not found", show_alert=True)
    lang = str(user.get("lang") or "en")

    if kind == "close":
        await store.clear_pending_reply(user_id)
        await store.track_event(user_id, "ticket_closed_without_reply")
        return await callback.answer("Тикет закрыт")

    if kind == "paywall":
        market = str(user.get("market") or "global")
        try:
            await bot.send_message(
                user_id,
                paywall_text(lang, market),
                reply_markup=keyboards.premium_kb(lang, market, has_recurring=bool(user.get("subscription_recurring"))),
            )
            now = datetime.now(timezone.utc)
            await store.update_user(user_id, sales_stage="offer_seen", last_offer_at=now.isoformat(), last_admin_reply_at=now.isoformat())
            await store.add_message(user_id, "assistant", "[paywall sent]")
            await store.clear_pending_reply(user_id)
            await store.track_event(user_id, "admin_paywall_sent")
            await store.track_event(user_id, "paywall_view", {"market": market, "source": "admin"})
            await _schedule_offer_followups(user_id, market)
            return await callback.answer("Тарифы отправлены")
        except TelegramForbiddenError:
            await store.mark_blocked(user_id)
            return await callback.answer("Пользователь заблокировал бота", show_alert=True)

    if kind not in {"private", "content", "expensive", "buy", "later"}:
        return await callback.answer("Unknown template", show_alert=True)
    body = quick_reply(lang, kind, user_id, str(user.get("first_name") or ""))
    result = await _send_admin_text(bot, user_id, body, f"admin_quick_reply_{kind}")
    await store.track_event(user_id, "admin_quick_reply", {"kind": kind})
    await callback.answer(result[:180])


@router.message(Command("broadcast"), F.from_user.id == settings.admin_id)
async def admin_broadcast(message: Message, command: CommandObject, bot: Bot) -> None:
    raw = (command.args or "").strip()
    if not raw:
        return await message.answer("Usage: /broadcast [segment] text")
    first, sep, rest = raw.partition(" ")
    segment_keys = {"all", "free", "paid", *MARKETS, *LANGS}
    segment = first.lower() if first.lower() in segment_keys else "all"
    body = rest.strip() if first.lower() in segment_keys else raw
    if not body:
        return await message.answer("Добавь текст.")

    users = await store._request("GET", "users?blocked=eq.false&select=user_id,lang,market,is_premium,premium_until&limit=10000")
    targets = []
    for u in users:
        if segment in LANGS and u.get("lang") != segment:
            continue
        if segment in MARKETS and u.get("market") != segment:
            continue
        if segment == "paid" and not premium_is_active(u):
            continue
        if segment == "free" and premium_is_active(u):
            continue
        targets.append(u)

    sent = 0
    for u in targets:
        try:
            await bot.send_message(u["user_id"], body, parse_mode=None)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            await store.mark_blocked(int(u["user_id"]))
        except Exception:
            logger.exception("Broadcast failed for %s", u["user_id"])
    await message.answer(f"Доставлено: {sent}/{len(targets)} · segment={segment}")


# Reply with text to a ticket header.
@router.message(F.reply_to_message & F.text, F.from_user.id == settings.admin_id)
async def admin_ticket_text_reply(message: Message, bot: Bot) -> None:
    source = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"TICKET_ID:\s*(\d+)", source)
    if not match:
        return
    result = await _send_admin_text(bot, int(match.group(1)), compact_text(message.text, 4000), "admin_reply")
    await message.reply(html.escape(result))


# Reply with media to a ticket header; the media is copied to the user as-is.
@router.message(
    F.reply_to_message & (F.photo | F.video | F.voice | F.audio | F.document | F.animation | F.sticker),
    F.from_user.id == settings.admin_id,
)
async def admin_ticket_media_reply(message: Message, bot: Bot) -> None:
    source = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"TICKET_ID:\s*(\d+)", source)
    if not match:
        return
    user_id = int(match.group(1))
    if not await store.get_user(user_id):
        return await message.reply("User not found.")
    try:
        await bot.copy_message(user_id, message.chat.id, message.message_id)
        placeholder = message.caption or "[media from Victoria]"
        result = await _after_admin_reply(user_id, placeholder, "admin_media_reply")
        await message.reply(result)
    except TelegramForbiddenError:
        await store.mark_blocked(user_id)
        await message.reply("Пользователь заблокировал бота.")


# ---------------------------- User inbox --------------------------------

@router.message(F.text & ~F.text.startswith("/"))
async def user_text(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    if user_id == settings.admin_id:
        return
    async with _lock(user_id):
        user = await store.get_user(user_id)
        lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
        if not user or not user.get("onboarding_complete") or not user.get("region_confirmed"):
            return await message.answer(t(lang, "not_ready"))
        if not await _ensure_public_for_message(message, bot, user):
            return
        body = compact_text(message.text or "", 4000)
        if body:
            await _receive_user_chat(message, bot, user, body, paid_chat=is_paid_chat_reply(message, _tier(user)))


async def _receive_user_chat(
    message: Message, bot: Bot, user: dict, body: str, *, paid_chat: bool = False,
) -> None:
    """Preserve the old inbox and add a separately tracked Pro+ chat path."""
    user_id = message.from_user.id
    tier = _tier(user)
    if paid_chat and tier not in PAID_CHAT_TIERS:
        return
    kind = "premium_chat_message" if paid_chat else "chat_message"
    for label, operation in [
        ("message_log", store.add_message(user_id, "user", body)),
        ("chat_activity", store.record_chat_activity(user_id)),
        ("cancel_followups", store.cancel_jobs(user_id, OFFER_JOB_TYPES + CHECKOUT_JOB_TYPES)),
        ("queue_reply", store.queue_reply(user_id)),
        ("event", store.track_event(user_id, kind, {"tier": tier, "type": "text"})),
    ]:
        try:
            await operation
        except Exception:
            logger.exception("Chat bookkeeping failed: %s user=%s", label, user_id)
    try:
        fresh = await store.get_user(user_id) or user
    except Exception:
        fresh = user
    await _notify_admin(message, bot, fresh, body, paid_chat=paid_chat)


@router.message(F.photo | F.video | F.voice | F.audio | F.document | F.animation | F.sticker)
async def user_media(message: Message, bot: Bot) -> None:
    if message.from_user.id == settings.admin_id:
        return
    user_id = message.from_user.id
    user = await store.get_user(user_id)
    lang = str((user or {}).get("lang") or normalize_lang(message.from_user.language_code))
    if not user or not user.get("onboarding_complete") or not user.get("region_confirmed"):
        return await message.answer(t(lang, "not_ready"))
    if not await _ensure_public_for_message(message, bot, user):
        return
    description = compact_text(message.caption or "[media]", 4000)
    for label, operation in [
        ("message_log", store.add_message(user_id, "user", description)),
        ("chat_activity", store.record_chat_activity(user_id)),
        ("cancel_followups", store.cancel_jobs(user_id, OFFER_JOB_TYPES + CHECKOUT_JOB_TYPES)),
        ("queue_reply", store.queue_reply(user_id)),
        ("event", store.track_event(user_id, "chat_message", {"tier": _tier(user), "type": "media"})),
    ]:
        try:
            await operation
        except Exception:
            logger.exception("Media bookkeeping failed: %s user=%s", label, user_id)
    try:
        fresh = await store.get_user(user_id) or user
    except Exception:
        fresh = user
    await _notify_admin(message, bot, fresh, description, media=True)
