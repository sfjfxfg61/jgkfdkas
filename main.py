"""Victoria Simple: subscription checkout, region-specific prices, access, admin inbox.

No conversational AI, forced joins or fake countdowns.
Uses existing Supabase tables without destructive migrations.
"""
from __future__ import annotations
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
import html
import logging
import re
from zoneinfo import ZoneInfo

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from inbox import InboxMiddleware
from analytics import detailed_report, chunks as report_chunks
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import (CallbackQuery, ChatJoinRequest, InlineKeyboardButton,
                           InlineKeyboardMarkup, LabeledPrice, Message, PreCheckoutQuery)

from catalog import (PERPETUAL, MARKETS, active, clean_market, default_market,
                     entitlement, new_payload, parse_invoice, parse_payload, plans)
from config import cfg
from storage import store, now_iso
from words import LANGS, t
from reminder_schedule import should_send_today

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('victoria.simple')
router = Router()
router.message.filter(F.chat.type == 'private')
router.message.outer_middleware(InboxMiddleware(store, cfg, lang_of=lambda u, tg: lang_of(u, tg)))
_start_re = re.compile(r'^[a-zA-Z0-9_]{1,48}$')


# Public channel links are created only for configured language-specific channels.
# Telegram numeric channel IDs require admin permission to create invite links.
_public_cache: dict[str, str] = {}


async def public_channel_link(bot: Bot, lang: str) -> str | None:
    entry = cfg.public_for(lang)
    if not entry:
        return None
    if entry.startswith('https://t.me/') or entry.startswith('http://t.me/'):
        return entry.replace('http://t.me/', 'https://t.me/', 1)
    if entry.startswith('@'):
        return 'https://t.me/' + entry[1:]
    if entry in _public_cache:
        return _public_cache[entry]
    try:
        chat_id = int(entry)
        chat = await bot.get_chat(chat_id)
        if getattr(chat, 'username', None):
            url = 'https://t.me/' + chat.username
        else:
            invite = await bot.create_chat_invite_link(chat_id, name='public-victoria')
            url = str(invite.invite_link)
        _public_cache[entry] = url
        return url
    except Exception:
        log.warning('Public channel link unavailable for lang=%s; check PUB_LINK_* and channel permissions', lang)
        return None


async def public_channel_button(bot: Bot, lang: str) -> list[InlineKeyboardButton]:
    url = await public_channel_link(bot, lang)
    return [InlineKeyboardButton(text='📣 ' + t(lang, 'public_channel'), url=url)] if url else []


def lang_of(u: dict | None, telegram_lang: str | None = None) -> str:
    existing = (u or {}).get('lang')
    if existing in LANGS:
        return existing
    code = (telegram_lang or '').split('-')[0].lower()
    return 'uk' if code == 'ua' else code if code in LANGS else 'en'


def menu(lang: str, alerts: bool = False):
    rows = [
        [InlineKeyboardButton(text='📣 ' + t(lang, 'public_channel'), callback_data='menu:public')],
        [InlineKeyboardButton(text=t(lang, 'plans'), callback_data='menu:plans')],
        [InlineKeyboardButton(text=t(lang, 'access'), callback_data='menu:access')],
        [InlineKeyboardButton(text=t(lang, 'support'), callback_data='menu:support')],
        [InlineKeyboardButton(text='🌍 Region / Регион', callback_data='menu:regions'),
         InlineKeyboardButton(text='🌐 Language / Мова', callback_data='menu:languages')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def region_keyboard(lang: str, selected: str):
    # Region is explicitly selected by the user, not an inferred physical location.
    captions = {'ua': '🇺🇦 Україна', 'cis': '🌐 CIS', 'latam': '🌎 LATAM',
                'asia': '🌏 Asia', 'eu': '🇪🇺 EU', 'us': '🇺🇸 US', 'global': '🌍 Global'}
    rows = [[InlineKeyboardButton(text=(('✅ ' if name == selected else '') + captions[name]),
                                   callback_data='region:' + name)] for name in MARKETS]
    rows.append([InlineKeyboardButton(text=t(lang, 'back'), callback_data='menu:home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def promo_deadline(user: dict | None) -> int | None:
    if not user or clean_market(user.get('market')) not in ('eu', 'us', 'global'):
        return None
    raw = user.get('vip_offer_expires_at')
    try:
        expiry = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        if expiry.tzinfo and datetime.now(timezone.utc) < expiry:
            return int(expiry.timestamp())
    except (TypeError, ValueError):
        pass
    return None


def offer_price(market: str, code: str, deadline: int | None) -> int:
    return 500 if code == 'vip' and clean_market(market) in ('eu', 'us', 'global') and deadline else plans(market)[code].stars


def plans_fallback_keyboard(lang: str, market: str, deadline: int | None = None):
    p = plans(market)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'{t(lang, "button_trial")} · {p["trial"].stars} ⭐', callback_data='buy:trial')],
        [InlineKeyboardButton(text=f'{t(lang, "button_forever")} · {p["forever"].stars} ⭐', callback_data='buy:forever')],
        [InlineKeyboardButton(text=f'{t(lang, "button_vip")} · {offer_price(market, "vip", deadline)} ⭐', callback_data='buy:vip')],
        [InlineKeyboardButton(text=t(lang, 'back'), callback_data='menu:home')],
    ])


async def plans_keyboard(lang: str, market: str, bot: Bot, user_id: int, deadline: int | None = None):
    """One click opens Telegram's official Stars purchase flow.

    If Telegram cannot mint invoice deep links, fall back to old callbacks.
    """
    p = plans(market)
    labels = {code: t(lang, 'button_' + code) for code in ('trial', 'forever', 'vip')}
    buttons = []
    try:
        for code, plan in p.items():
            price = offer_price(market, code, deadline)
            link = await bot.create_invoice_link(
                title=t(lang, 'invoice_title_' + code)[:32],
                description=t(lang, 'invoice_' + code, vip_days=cfg.vip_days)[:255],
                payload=new_payload(user_id, code, market, promo_until=deadline if code == 'vip' else None),
                provider_token='', currency='XTR',
                prices=[LabeledPrice(label=t(lang, 'invoice_title_' + code), amount=price)],
            )
            buttons.append([InlineKeyboardButton(text=f'{labels[code]} · {price} ⭐', url=link)])
    except Exception:
        log.exception('Direct invoice links failed; using callback fallback uid=%s', user_id)
        return plans_fallback_keyboard(lang, market, deadline)
    buttons.append([InlineKeyboardButton(text=t(lang, 'back'), callback_data='menu:home')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_plans(msg: Message, bot: Bot, user: dict):
    uid = int(user['user_id']); lg = lang_of(user)
    market = clean_market(user.get('market'))
    await store.patch(uid, last_offer_at=now_iso(), sales_stage='offer_seen')
    await store.event(uid, 'simple_offer_seen', market=market)
    await msg.answer(summary_text(lg, market) + ('\n\n👑 VIP promo: 500 ⭐ · 2h' if promo_deadline(user) else ''), reply_markup=await plans_keyboard(lg, market, bot, uid, promo_deadline(user)))


def language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Русский', callback_data='lang:ru'),
         InlineKeyboardButton(text='Українська', callback_data='lang:uk')],
        [InlineKeyboardButton(text='English', callback_data='lang:en'),
         InlineKeyboardButton(text='Deutsch', callback_data='lang:de')],
        [InlineKeyboardButton(text='Español', callback_data='lang:es'),
         InlineKeyboardButton(text='Français', callback_data='lang:fr')],
    ])


def notify_keyboard(lang: str, opted: bool):
    # Compatibility with messages sent by older versions: no opt-out control.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'remind_off'), callback_data='notify:off')],
        [InlineKeyboardButton(text=t(lang, 'back'), callback_data='menu:home')],
    ])


def summary_text(lang: str, market: str = "global"):
    p = plans(market)
    return t(lang, 'buy', trial=p['trial'].stars, forever=p['forever'].stars,
             vip=p['vip'].stars, vip_days=cfg.vip_days) + f'\n\n🌍 {market.upper()}'


async def admin_alert(bot: Bot, text: str):
    try:
        await bot.send_message(cfg.admin_id, text)
    except Exception:
        log.exception('Admin alert delivery failed')


async def reg(tg, ref: str = 'direct'):
    old = await store.get_user(tg.id)
    return await store.upsert_user(tg, lang_of(old, tg.language_code), ref)


async def send_home(msg: Message, bot: Bot, user: dict):
    lg = lang_of(user)
    if active(user):
        await msg.answer(t(lg, 'hello'), reply_markup=menu(lg))
        return
    uid = int(user['user_id']); market = clean_market(user.get('market'))
    await store.patch(uid, last_offer_at=now_iso(), sales_stage='offer_seen')
    await store.event(uid, 'simple_offer_seen', market=market, source='start')
    kb = await plans_keyboard(lg, market, bot, uid, promo_deadline(user))
    rows = [list(row) for row in kb.inline_keyboard if row[0].callback_data != 'menu:home']
    public_button = await public_channel_button(bot, lg)
    if public_button:
        rows.insert(0, public_button)
    rows.extend([
        [InlineKeyboardButton(text=t(lg, 'support'), callback_data='menu:support'),
         InlineKeyboardButton(text=t(lg, 'access'), callback_data='menu:access')],
        [InlineKeyboardButton(text='🌍 Region', callback_data='menu:regions')],
        [InlineKeyboardButton(text='🌐 Language', callback_data='menu:languages')],
    ])
    await msg.answer(summary_text(lg, market) + ('\n\n👑 VIP promo: 500 ⭐ · 2h' if promo_deadline(user) else ''), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.message(CommandStart())
async def start(message: Message, bot: Bot):
    if not message.from_user:
        return
    raw = (message.text or '').split(maxsplit=1)
    ref = raw[1].strip() if len(raw) == 2 and _start_re.fullmatch(raw[1].strip()) else 'direct'
    user = await reg(message.from_user, ref)
    await store.event(message.from_user.id, 'simple_start', ref=ref)
    if message.from_user.id == cfg.admin_id:
        await admin_home(message)
    else:
        await send_home(message, bot, user)


@router.message(Command('plans', 'buy'))
async def command_plans(message: Message, bot: Bot):
    if not message.from_user:
        return
    user = await reg(message.from_user)
    await show_plans(message, bot, user)


@router.message(Command('access'))
async def command_access(message: Message, bot: Bot):
    if not message.from_user:
        return
    user = await reg(message.from_user)
    await display_access(message, bot, user)


async def fresh_invite(bot: Bot, uid: int) -> str:
    # Only paid users' join requests are subsequently approved. Link expires for real.
    invite = await bot.create_chat_invite_link(
        cfg.private_id, name=f'victoria-{uid}'[:32],
        expire_date=datetime.now(timezone.utc) + timedelta(hours=12),
        creates_join_request=True,
    )
    return str(invite.invite_link)


async def display_access(msg: Message, bot: Bot, user: dict):
    lg = lang_of(user)
    uid = int(user['user_id'])
    if not active(user):
        await msg.answer(t(lg, 'not_paid'), reply_markup=await plans_keyboard(lg, clean_market(user.get('market')), bot, uid, promo_deadline(user)))
        return
    try:
        link = await fresh_invite(bot, uid)
    except Exception:
        log.exception('Paid invite failed for user=%s', uid)
        await store.event(uid, 'simple_invite_failed')
        await admin_alert(bot, f'🚨 Канал: ошибка инвайта для <code>{uid}</code>. Проверь права бота.')
        await msg.answer(t(lg, 'access_error'), reply_markup=menu(lg))
        return
    await store.event(uid, 'simple_invite_created')
    await msg.answer(t(lg, 'paid') + '\n\n' + html.escape(link), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lg, 'join'), url=link)],
        [InlineKeyboardButton(text=t(lg, 'home'), callback_data='menu:home')],
    ]))
    await store.event(uid, 'simple_invite_sent')


@router.callback_query(F.data.startswith('menu:'))
async def open_menu(c: CallbackQuery, bot: Bot):
    user = await reg(c.from_user)
    lg = lang_of(user)
    where = c.data.split(':', 1)[1]
    await c.answer()
    if where == 'plans':
        await show_plans(c.message, bot, user)
    elif where == 'access':
        await display_access(c.message, bot, user)
    elif where == 'support':
        await c.message.answer(t(lg, 'ask_support'))
    elif where == 'public':
        button = await public_channel_button(bot, lg)
        if button:
            await c.message.answer(t(lg, 'public_channel'),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[button]))
        else:
            await c.message.answer(t(lg, 'public_unavailable'))
    elif where == 'notify':
        enabled = True
        await c.message.answer(t(lg, 'notify_on') if enabled else t(lg, 'notify_off'),
                               reply_markup=notify_keyboard(lg, enabled))
    elif where == 'languages':
        await c.message.answer('🌐 Language', reply_markup=language_keyboard())
    elif where == 'regions':
        await c.message.answer('🌍 Region / Регион', reply_markup=region_keyboard(lg, clean_market(user.get('market'))))
    else:
        await c.message.answer(t(lg, 'hello'), reply_markup=menu(lg))


@router.callback_query(F.data.startswith('lang:'))
async def set_language(c: CallbackQuery):
    lg = c.data.split(':', 1)[1]
    if lg not in LANGS:
        return await c.answer()
    await reg(c.from_user)
    await store.patch(c.from_user.id, lang=lg)
    await c.answer()
    await c.message.answer(t(lg, 'hello'), reply_markup=menu(lg))


@router.callback_query(F.data.startswith('region:'))
async def set_region(c: CallbackQuery, bot: Bot):
    code = c.data.split(':', 1)[1]
    if code not in MARKETS:
        await c.answer('Invalid region', show_alert=True)
        return
    user = await reg(c.from_user)
    user = await store.patch(c.from_user.id, market=code, region_confirmed=True)
    await store.event(c.from_user.id, 'simple_market_selected', market=code)
    await c.answer()
    await show_plans(c.message, bot, user)


@router.callback_query(F.data.startswith('notify:'))
async def set_notification(c: CallbackQuery):
    user = await reg(c.from_user)
    lg = lang_of(user)
    enabled = c.data != 'notify:off'
    await store.patch(c.from_user.id, automation_paused=not enabled)
    await c.answer()
    await c.message.answer(t(lg, 'notify_on' if enabled else 'notify_off'), reply_markup=notify_keyboard(lg, enabled))


@router.callback_query(F.data.startswith('buy:'))
async def pay(c: CallbackQuery, bot: Bot):
    plan_code = c.data.split(':', 1)[1]
    if plan_code not in plans():
        await c.answer('Invalid plan', show_alert=True)
        return
    user = await reg(c.from_user)
    lg = lang_of(user)
    market = clean_market(user.get('market'))
    plan = plans(market)[plan_code]
    deadline = promo_deadline(user)
    amount = offer_price(market, plan_code, deadline)
    payload = new_payload(c.from_user.id, plan_code, market, promo_until=deadline if plan_code == 'vip' else None)
    # Pre-checkout is answered immediately without Supabase round trip.
    try:
        await bot.send_invoice(
            chat_id=c.from_user.id,
            title=t(lg, 'invoice_title_' + plan_code)[:32],
            description=t(lg, 'invoice_' + plan_code, vip_days=cfg.vip_days)[:255],
            payload=payload,
            provider_token='', currency='XTR',
            prices=[LabeledPrice(label=t(lg, 'invoice_title_' + plan_code), amount=amount)],
        )
    except Exception:
        log.exception('Invoice error uid=%s plan=%s', c.from_user.id, plan_code)
        await store.event(c.from_user.id, 'simple_invoice_error', plan=plan_code)
        await c.answer(t(lg, 'invoice_error'), show_alert=True)
        return
    await c.answer()
    try:
        await store.patch(c.from_user.id, sales_stage='checkout_started', last_checkout_at=now_iso())
        await store.event(c.from_user.id, 'simple_checkout', plan=plan_code, stars=amount)
    except Exception:
        log.exception('Optional invoice bookkeeping failed')
    await admin_alert(bot, f'⚡ <b>Клик оплаты</b>\nID: <code>{c.from_user.id}</code>\n'
                           f'Юзер: @{html.escape(c.from_user.username or "нет")}\n'
                           f'Тариф: <b>{plan_code}</b> ({amount} ⭐)')


@router.pre_checkout_query()
async def confirm_checkout(q: PreCheckoutQuery, bot: Bot):
    details = parse_invoice(q.invoice_payload, q.from_user.id, q.total_amount) if q.currency == 'XTR' else None
    await q.answer(ok=details is not None,
                   error_message=None if details else 'Please open a fresh invoice in the bot.')
    if details:
        # Only fired when user proceeds to Telegram's payment confirmation.
        asyncio.create_task(store.event(q.from_user.id, 'simple_checkout', plan=details.code,
                                        stars=details.amount, market=details.market))
        asyncio.create_task(admin_alert(bot,
            f'⚡ <b>Попытка оплаты</b>\nID: <code>{q.from_user.id}</code>\n'
            f'Тариф: {html.escape(details.code)} · {details.amount} ⭐\n'
            f'Регион: {html.escape(details.market)}'))


async def activate_paid(message: Message, bot: Bot):
    if not message.from_user or not message.successful_payment:
        return
    tg = message.from_user
    payment = message.successful_payment
    try:
        user = await reg(tg)
    except Exception:
        log.exception('CRITICAL: registration failed after confirmed Stars purchase')
        await admin_alert(bot,
            f'🚨 Telegram подтвердил Stars: user <code>{tg.id}</code>, '
            f'charge <code>{html.escape(payment.telegram_payment_charge_id)}</code>, '
            f'amount <b>{payment.total_amount} ⭐</b>. БД недоступна; восстановить вручную.')
        await message.answer('Payment received. Please contact support if access is delayed.')
        return
    details = parse_invoice(payment.invoice_payload, tg.id, payment.total_amount, allow_expired=True)
    code = details.code if details else None
    if not code:
        # Real Telegram successful_payment from a previous bot version may still arrive.
        # Preserve evidence, don't misrepresent it as a completed simple purchase.
        code = 'legacy_review'
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        duration = 30
    else:
        expires = entitlement(user, code)
        duration = plans()[code].days
    charge = payment.telegram_payment_charge_id
    try:
        receipt, duplicate = await store.save_receipt(
            tg.id, charge, payment.invoice_payload, payment.total_amount,
            code, duration, expires, details.market if details else str(user.get('market') or 'global'))
        await store.grant_from_receipt(receipt)
        if not duplicate:
            try: await accrue_partner_commission(tg.id, receipt)
            except Exception: log.exception("Commission accrual failed for payment %s", receipt.get("id"))
    except Exception:
        log.exception('CRITICAL: Telegram paid but DB activation failed user=%s', tg.id)
        await admin_alert(bot,
            f'🚨 <b>ОПЛАТА ПОДТВЕРЖДЕНА, НО АКТИВАЦИЯ НЕ УДАЛАСЬ</b>\n'
            f'User <code>{tg.id}</code>, charge <code>{html.escape(charge)}</code>. '
            'Нужно проверить БД и выполнить /repair.')
        await message.answer('✅ Telegram confirmed your payment. Support will restore access; no need to pay again.')
        return
    if not duplicate:
        await store.event(tg.id, 'simple_payment_success', plan=code,
                          charge_id=charge, stars=payment.total_amount)
        await admin_alert(bot, f'💰 <b>НОВАЯ ОПЛАТА</b>\n'
                         f'ID: <code>{tg.id}</code>\nТариф: {html.escape(code)}\n'
                         f'Сумма: {payment.total_amount} ⭐\n'
                         f'Charge: <code>{html.escape(charge)}</code>')
    if code == 'legacy_review':
        await admin_alert(bot, f'⚠️ Legacy invoice, review its original terms. User: <code>{tg.id}</code>')
    await message.answer(t(lang_of(user), 'payment_success'))
    fresh = await store.get_user(tg.id)
    await display_access(message, bot, fresh)


@router.message(F.successful_payment)
async def confirmed_payment(message: Message, bot: Bot):
    await activate_paid(message, bot)


@router.message(F.refunded_payment)
async def refund_handler(msg: Message, bot: Bot):
    if not msg.from_user or not msg.refunded_payment:
        return
    uid = msg.from_user.id
    charge = msg.refunded_payment.telegram_payment_charge_id
    try:
        receipt = await store.refund_receipt(charge)
        user = await store.get_user(uid)
        if receipt and user and user.get('subscription_charge_id') == charge:
            other = await store.all_rows('payments', 'id,user_id,amount,plan,telegram_charge_id,entitlement_until,refunded_at,payload',
                      {'user_id': f'eq.{uid}', 'refunded_at': 'is.null', 'order': 'entitlement_until.desc'}, 100)
            if other:
                # Restore any other valid entitlement before considering revocation.
                await store.patch(uid, is_paid=False, is_premium=False, premium_until=None,
                                  subscription_tier='free', subscription_charge_id=None)
                await store.grant_from_receipt(other[0])
            else:
                await store.patch(uid, is_paid=False, is_premium=False,
                                  premium_until=None, subscription_tier='free',
                                  subscription_charge_id=None, sales_stage='refunded')
                try:
                    await bot.ban_chat_member(cfg.private_id, uid)
                    await bot.unban_chat_member(cfg.private_id, uid, only_if_banned=True)
                except Exception:
                    log.exception('Refund confirmed but channel removal failed uid=%s', uid)
        await admin_alert(bot, f'↩️ <b>Refund Stars</b> uid=<code>{uid}</code> '
                               f'charge=<code>{html.escape(charge)}</code> '
                               f'found_in_db={bool(receipt)}')
        await store.event(uid, 'simple_refund', charge_id=charge)
    except Exception:
        log.exception('Failed to process Telegram Stars refund uid=%s', uid)
        await admin_alert(bot, f'🚨 Refund event processing failed uid=<code>{uid}</code>, '
                               f'charge=<code>{html.escape(charge)}</code>')


@router.chat_join_request()
async def join_request(req: ChatJoinRequest, bot: Bot):
    if req.chat.id != cfg.private_id:
        return
    user = await store.get_user(req.from_user.id)
    if active(user):
        await bot.approve_chat_join_request(cfg.private_id, req.from_user.id)
        await store.patch(req.from_user.id, channel_member=True)
        await store.event(req.from_user.id, 'simple_join_approved')
    else:
        await bot.decline_chat_join_request(cfg.private_id, req.from_user.id)


@router.message(Command('support', 'help'))
async def help_command(message: Message):
    if not message.from_user:
        return
    u = await reg(message.from_user)
    await message.answer(t(lang_of(u), 'ask_support'))


@router.message(Command('reminders'))
async def reminders_command(message: Message):
    if not message.from_user:
        return
    u = await reg(message.from_user)
    lg = lang_of(u)
    await message.answer(t(lg, 'notifications'),
                         reply_markup=notify_keyboard(lg, True))


# ---------- Admin ----------
def admin(msg: Message) -> bool:
    return bool(msg.from_user and msg.from_user.id == cfg.admin_id)


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 Статистика', callback_data='admin:stats'),
         InlineKeyboardButton(text='💬 Обращения', callback_data='admin:pending')],
        [InlineKeyboardButton(text='⭐ Платежи', callback_data='admin:payments'),
         InlineKeyboardButton(text='🌍 Регионы', callback_data='admin:regions')],
        [InlineKeyboardButton(text='🤝 Заливщики', callback_data='admin:partners')],
        [InlineKeyboardButton(text='🧲 Воронка', callback_data='admin:funnel'),
         InlineKeyboardButton(text='🔔 Напоминания', callback_data='admin:reminders')],
    ])


@router.callback_query(F.data.startswith('admin:'))
async def admin_callback(c: CallbackQuery):
    if c.from_user.id != cfg.admin_id:
        await c.answer('Access denied', show_alert=True)
        return
    await c.answer()
    if c.data == 'admin:stats':
        await admin_stats(c.message, from_button=True)
    elif c.data == 'admin:pending':
        await admin_pending(c.message, from_button=True)
    elif c.data == 'admin:payments':
        await admin_payments(c.message, from_button=True)
    elif c.data == 'admin:regions':
        await admin_regions(c.message, from_button=True)
    elif c.data == 'admin:funnel':
        await admin_funnel(c.message, from_button=True)
    elif c.data == 'admin:partners':
        await admin_partners(c.message, from_button=True)
    elif c.data == 'admin:reminders':
        await admin_reminder_stats(c.message, from_button=True)


# ---------- Traffic partners ----------
@router.message(Command('partners'))
async def admin_partners(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    partners = await store.all_rows('traffic_partners', '*', {'order': 'id.asc'}, None)
    users = await store.all_rows('users', 'user_id,ref', {}, None)
    commissions = await store.all_rows('traffic_commissions', '*', {}, None)
    payouts = await store.all_rows('partner_payouts', '*', {}, None)
    payments = await store.all_rows('payments', 'id,refunded_at', {}, None)
    refunded = {int(p['id']) for p in payments if p.get('refunded_at')}
    counts = Counter(str(u.get('ref') or '') for u in users)
    lines = ['🤝 <b>Заливщики</b>']
    for partner in partners:
        pid = int(partner['id']); code = str(partner['code'])
        earned = sum(int(c['commission_stars']) for c in commissions if int(c['partner_id']) == pid and int(c['payment_id']) not in refunded)
        paid = sum(int(c['amount_stars']) for c in payouts if int(c['partner_id']) == pid)
        purchases = sum(1 for c in commissions if int(c['partner_id']) == pid)
        lines.append(f"\n<b>{html.escape(str(partner['display_name']))}</b> ({html.escape(code)})"
                     f"\nПривёл: {counts[code]} · продаж: {purchases}"
                     f"\nНачислено: {earned} ⭐ · выплачено: {paid} ⭐ · остаток: {earned-paid} ⭐"
                     f"\nСтавка: {partner['commission_pct']}% · {'активен' if partner['active'] else 'выключен'}"
                     f"\nСсылка: https://t.me/{(await msg.bot.get_me()).username}?start={code}")
    lines.append('\n/addpartner ID код название — добавить (30%)'
                 '\n/partnerpct код процент — изменить ставку'
                 '\n/partneroff код — выключить; /partneron код — включить'
                 '\n/partnerpay код сумма — записать выплату в Stars')
    await msg.answer('\n'.join(lines)[:4000], disable_web_page_preview=True)

@router.message(Command('addpartner'))
async def add_partner(msg: Message):
    if not admin(msg): return
    parts = (msg.text or '').split(maxsplit=3)
    if len(parts) < 4 or not parts[1].isdigit() or not re.fullmatch(r'[a-z0-9_]{3,32}', parts[2]):
        await msg.answer('Формат: /addpartner TELEGRAM_ID code Имя'); return
    try:
        await store.req('POST','traffic_partners',body={'telegram_user_id':int(parts[1]), 'code':parts[2], 'display_name':parts[3], 'commission_pct':30},prefer='return=minimal')
        await msg.answer('✅ Заливщик добавлен. /partners')
    except Exception as exc: await msg.answer('Ошибка добавления: '+html.escape(str(exc)[:200]))

@router.message(Command('partnerpct','partneroff','partneron','partnerpay'))
async def partner_manage(msg: Message):
    if not admin(msg): return
    parts=(msg.text or '').split()
    cmd=parts[0].split('@')[0].lstrip('/')
    if len(parts) != (3 if cmd in ('partnerpct','partnerpay') else 2):
        await msg.answer('Неверные аргументы. См. /partners'); return
    rows=await store.req('GET','traffic_partners',params={'code':'eq.'+parts[1], 'select':'*','limit':'1'})
    if not rows: await msg.answer('Код не найден'); return
    partner=rows[0]
    if cmd in ('partneroff','partneron'):
        await store.req('PATCH','traffic_partners',params={'id':'eq.'+str(partner['id'])},body={'active':cmd=='partneron'},prefer='return=minimal')
    elif cmd=='partnerpct':
        try: rate=float(parts[2]); assert 0<=rate<=100
        except (ValueError,AssertionError): await msg.answer('Процент должен быть 0–100'); return
        await store.req('PATCH','traffic_partners',params={'id':'eq.'+str(partner['id'])},body={'commission_pct':rate},prefer='return=minimal')
    else:
        try: amount=int(parts[2]); assert amount>0
        except (ValueError,AssertionError): await msg.answer('Сумма должна быть положительной'); return
        await store.req('POST','partner_payouts',body={'partner_id':partner['id'],'amount_stars':amount,'note':'Manual admin record'},prefer='return=minimal')
    await msg.answer('✅ Сохранено. /partners')

async def accrue_partner_commission(user_id: int, receipt: dict):
    """Idempotent by UNIQUE payment_id; only new, non-refunded XTR receipts."""
    if receipt.get('refunded_at') or receipt.get('currency') != 'XTR': return
    u=await store.get_user(user_id)
    code=(u or {}).get('ref')
    if not code: return
    rows=await store.req('GET','traffic_partners',params={'code':'eq.'+str(code),'active':'eq.true','select':'*','limit':'1'})
    if not rows: return
    partner=rows[0]
    if int(partner['telegram_user_id'])==user_id: return
    from decimal import Decimal, ROUND_HALF_UP
    pct=Decimal(str(partner['commission_pct']))
    stars=int((Decimal(int(receipt['amount']))*pct/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    try:
        await store.req('POST','traffic_commissions',body={'partner_id':partner['id'],'payment_id':receipt['id'],'user_id':user_id,'gross_stars':receipt['amount'],'commission_pct':str(pct),'commission_stars':stars},prefer='return=minimal')
    except Exception:
        # Could be a duplicate payment; do not generate another commission.
        existing=await store.req('GET','traffic_commissions',params={'payment_id':'eq.'+str(receipt['id']),'select':'id','limit':'1'})
        if not existing: raise

@router.message(Command('admin'))
async def admin_home(msg: Message):
    if not admin(msg):
        return
    await msg.answer('💜 <b>Victoria Simple · админка</b>\n\n'
       '/stats — реальные показатели\n'
       '/payments — последние покупки\n'
       '/regions — регионы и тарифы\n'
       '/funnel — воронка\n'
       '/reminder_stats — напоминания\n'
       '/pending — обращения\n'
       '/user ID — профиль\n'
       '/messages ID — последние сообщения\n'
       '/send ID текст — ответить и закрыть обращение\n'
       '/repair — восстановить доступ по учтённым платежам\n'
       '/cancel_legacy_jobs — отменить старые задания рассылок (по запросу)', reply_markup=admin_keyboard())


@router.message(Command('stats'))
async def admin_stats(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    await msg.answer('⏳ Считаю подробную статистику...')
    try:
        for section in await detailed_report(store, cfg):
            await msg.answer(section)
    except Exception:
        log.exception('Detailed statistics unavailable')
        await msg.answer('❌ Не удалось прочитать все данные. Проверь доступ к таблицам БД; отчёт не выдаётся как полный.')


@router.message(Command('funnel'))
async def admin_funnel(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    ev = await store.all_rows('events', 'user_id,event,created_at',
        {'event': 'in.(simple_start,simple_offer_seen,simple_checkout,simple_payment_success)'}, 15000)
    by_event = {key: set() for key in ('simple_start','simple_offer_seen','simple_checkout','simple_payment_success')}
    by_recent = {key: set() for key in by_event}
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for item in ev:
        k = item['event']; uid = int(item['user_id'])
        by_event[k].add(uid)
        try:
            if datetime.fromisoformat(str(item['created_at']).replace('Z','+00:00')) >= cutoff:
                by_recent[k].add(uid)
        except (ValueError, TypeError):
            pass
    lines = ['🧲 <b>Victoria · Воронка уникальных пользователей</b>']
    for k, label in [('simple_start','Начали'),('simple_offer_seen','Увидели тарифы'),
                     ('simple_checkout','Перешли к подтверждению оплаты'),
                     ('simple_payment_success','Оплатили')]:
        lines.append(f'{label}: <b>{len(by_event[k])}</b> · 7д {len(by_recent[k])}')
    lines.append('Статистика событий только этой версии. Старые платежи учитываются отдельно.')
    await msg.answer('\n'.join(lines))


@router.message(Command('reminder_stats'))
async def admin_reminder_stats(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    users = await store.all_rows('users',
        'user_id,blocked,automation_paused,is_paid,is_premium,premium_until', {'order': 'user_id.asc'}, None)
    eligible = sum(not u.get('blocked') for u in users)
    events = await store.all_rows('events', 'event,created_at',
                                  {'event': 'eq.simple_reminder_sent', 'order': 'id.asc'}, None)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = sum(1 for x in events if x.get('created_at') and
                 datetime.fromisoformat(x['created_at'].replace('Z','+00:00')) >= cutoff)
    await msg.answer(f'🔔 <b>Напоминания</b>\n'
                     f'Окно: {html.escape(cfg.reminder_window_start)}–{html.escape(cfg.reminder_window_end)} · {html.escape(cfg.reminder_timezone)}\n'
                     f'Отправка включена: {cfg.followups}\n'
                     f'Доступные пользователи (включая Premium): {eligible}\n'
                     f'Отправлено: {len(events)} · за 7д: {recent}\n'
                     'Не чаще одного раза в сутки; всем доступным пользователям, включая покупателей.')


@router.message(Command('payments'))
async def admin_payments(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    rows = await store.all_rows('payments', 'id,user_id,amount,created_at,plan,market,refunded_at',
                                {'order': 'created_at.desc'}, 100)
    count = sum(p.get('refunded_at') is None for p in rows)
    total = sum(int(p['amount']) for p in rows if not p.get('refunded_at'))
    lines = [f'⭐ <b>Последние {len(rows)} записей</b> · {count} действительных · {total} ⭐',
             '⚠️ Здесь только записи payments; прежние доступы не потеряны.']
    for p in rows[:15]:
        lines.append(f'{"↩️" if p.get("refunded_at") else "💜"} '
                     f'{str(p.get("created_at") or "")[:16]} · '
                     f'{html.escape(str(p.get("plan") or "?"))} · '
                     f'{int(p["amount"])}⭐ · ID <code>{int(p["user_id"])}</code>')
    await msg.answer('\n'.join(lines))


@router.message(Command('regions'))
async def admin_regions(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    users = await store.all_rows('users', 'user_id,market,blocked', {}, 10000)
    ledger = await store.all_rows('payments', 'user_id,amount,market,refunded_at', {}, 10000)
    people = Counter(clean_market(u.get('market')) for u in users)
    rev = Counter()
    for payment in ledger:
        if not payment.get('refunded_at'):
            rev[clean_market(payment.get('market'))] += int(payment['amount'])
    total = sum(people.values())
    lines = [f'🌍 <b>Регионы</b> · пользователей {total}',
             'Цены: тест / безлимит / VIP']
    for market in MARKETS:
        p = plans(market)
        lines.append(f'<b>{market.upper()}</b>: {people[market]} чел · '
                     f'{rev[market]} ⭐ · {p["trial"].stars}/{p["forever"].stars}/{p["vip"].stars} ⭐')
    await msg.answer('\n'.join(lines))


@router.message(Command('pending'))
async def admin_pending(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    items = await store.pending()
    if not items:
        return await msg.answer('✅ Нет ожидающих ответов.')
    enriched = []
    for r in items:
        uid = int(r['user_id'])
        u = await store.get_user(uid)
        priority = bool(active(u) and (u or {}).get('subscription_tier') == 'vip')
        enriched.append((priority, r, u))
    enriched.sort(key=lambda entry: (not entry[0], str(entry[1]['updated_at'])))
    lines = []
    for priority, r, u in enriched[:25]:
        uid = int(r['user_id'])
        label = '👑' if priority else '•'
        lines.append(f'{label} <code>{uid}</code> — '
                     f'{html.escape(str((u or {}).get("first_name") or "?"))}'
                     f' · {str(r["updated_at"])[:16]}')
    await msg.answer('💬 <b>Ждут ответа</b>\n' + '\n'.join(lines) + '\n\n/send ID текст')


@router.message(Command('user'))
async def admin_user(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or '').split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return await msg.answer('/user 123456789')
    uid = int(parts[1]); u = await store.get_user(uid)
    if not u:
        return await msg.answer('Пользователь не найден')
    labels = {'premium_until': 'Доступ до', 'subscription_tier': 'Тариф',
              'last_active_at': 'Последняя активность', 'created_at': 'Регистрация',
              'last_admin_reply_at': 'Последний ответ администратора'}
    lines = [f'👤 <b>Полный профиль</b> · <code>{uid}</code>',
             f'Действующий доступ: {active(u)}']
    for key, value in u.items():
        lines.append(f'{html.escape(labels.get(key, key))}: {html.escape(str(value if value is not None else "—"))}')
    for section in report_chunks(lines):
        await msg.answer(section)


@router.message(Command('messages'))
async def admin_messages(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or '').split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return await msg.answer('/messages 123456789')
    rows = await store.recent_messages(int(parts[1]))
    if not rows:
        return await msg.answer('Сообщений нет.')
    await msg.answer('💬 История · ID <code>' + parts[1] + '</code> · последние 10 записей')
    for row in reversed(rows):
        text = str(row['role']) + ' · ' + str(row.get('created_at') or '') + '\n' + str(row['content'])
        for offset in range(0, len(text), 3500):
            await msg.answer(text[offset:offset + 3500], parse_mode=None)


@router.message(Command('send', 'reply'))
async def admin_send(msg: Message, bot: Bot):
    if not admin(msg):
        return
    parts = (msg.text or '').split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        return await msg.answer('/send 123456789 Текст ответа')
    uid = int(parts[1]); text = parts[2]
    u = await store.get_user(uid)
    if not u:
        return await msg.answer('Нет такого пользователя в базе')
    # Capture queue timestamp before delivery: new incoming messages won't be hidden.
    waiting = await store.req('GET', 'pending_replies',
                              params={'user_id': f'eq.{uid}', 'select': 'updated_at', 'limit': '1'})
    wait_time = waiting[0]['updated_at'] if waiting else None
    try:
        await bot.send_message(uid, text, parse_mode=None)
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        return await msg.answer('❌ Ответ не доставлен: ' + html.escape(str(exc)[:140]))
    # Never report false success for DB sync; warn if user received it but queue was not cleared.
    try:
        await store.message(uid, 'assistant', text)
        await store.patch(uid, last_admin_reply_at=now_iso())
        await store.ticket_closed(uid, wait_time)
        await msg.answer('✅ Отправлено. Очередь ответа обновлена.')
    except Exception:
        log.exception('Admin sent successfully but database sync failed uid=%s', uid)
        await msg.answer('⚠️ Доставлено пользователю, но БД/очередь не обновились.')


@router.message(Command('repair'))
async def admin_repair(msg: Message):
    if not admin(msg):
        return
    try:
        count = await store.restore_receipts()
        await msg.answer(f'✅ Сверка завершена: восстановлено доступов {count}. Старые VIP не сброшены.')
    except Exception:
        log.exception('Receipt restoration failed')
        await msg.answer('❌ Сверка не завершилась; проверь логи Render.')


@router.message(Command('cancel_legacy_jobs'))
async def cancel_legacy(msg: Message):
    if not admin(msg):
        return
    try:
        await store.req('PATCH', 'automation_jobs', params={'status': 'eq.pending'},
                        body={'status': 'cancelled'}, prefer='return=minimal')
        await msg.answer('✅ Старые ожидающие задания отмечены как cancelled; история отправок сохранена.')
    except Exception:
        log.exception('Could not cancel old jobs')
        await msg.answer('❌ Не удалось отменить задания.')


# InboxMiddleware delivers all incoming private messages, including commands/media.
@router.message(F.text)
async def user_message(msg: Message, bot: Bot):
    if not msg.from_user or msg.from_user.id == cfg.admin_id:
        return
    u = await store.get_user(msg.from_user.id)
    await msg.answer(t(lang_of(u, msg.from_user.language_code), 'support_received'))


@router.message()
async def other_message(msg: Message, bot: Bot):
    if not msg.from_user or msg.from_user.id == cfg.admin_id:
        return
    u = await store.get_user(msg.from_user.id)
    await msg.answer(t(lang_of(u, msg.from_user.language_code), 'support_received'))


async def reminders_loop(bot: Bot):
    """Once per day, distributed over a configurable Kyiv-time window.

    Recovers missed time after Render restarts; no process memory needed.
    Excludes blocked users and respects automation_paused. /start is required by Telegram.
    """
    zone = ZoneInfo(cfg.reminder_timezone)
    while True:
        await asyncio.sleep(65)
        if not cfg.followups:
            continue
        local = datetime.now(zone)
        # Avoid a database scan until at least the start of the daily window.
        start_minute = int(cfg.reminder_window_start[:2]) * 60 + int(cfg.reminder_window_start[3:])
        if local.hour * 60 + local.minute < start_minute:
            continue
        try:
            users = await store.all_rows('users',
                'user_id,lang,market,is_paid,is_premium,premium_until,blocked,automation_paused,last_reminder_at,vip_offer_expires_at',
                {'blocked': 'eq.false', 'order': 'user_id.asc'}, None)
            for u in users:
                if not should_send_today(u, local, cfg.reminder_timezone,
                                         cfg.reminder_window_start, cfg.reminder_window_end):
                    continue
                uid = int(u['user_id']); lg = lang_of(u)
                try:
                    market = clean_market(u.get('market'))
                    if active(u):
                        continue
                    deadline = None
                    if market in ('eu', 'us', 'global'):
                        deadline = int(datetime.now(timezone.utc).timestamp()) + 7200
                        # Persist first: direct invoice links and fallback callbacks use the same expiry.
                        await store.patch(uid, vip_offer_expires_at=datetime.fromtimestamp(deadline, timezone.utc).isoformat())
                    if deadline:
                        copy = {
                            'ru': '💜 Victoria\nСегодня VIP на 30 дней: 500 ⭐ вместо обычных 1000 ⭐. Предложение действует 2 часа с момента этого сообщения. Акции могут повторяться.',
                            'uk': '💜 Victoria\nСьогодні VIP на 30 днів: 500 ⭐ замість звичайних 1000 ⭐. Пропозиція діє 2 години з моменту повідомлення. Акції можуть повторюватися.',
                            'en': '💜 Victoria\nVIP for 30 days: 500 ⭐ instead of the usual 1000 ⭐. Valid for 2 hours from this message. Offers may return.',
                            'de': '💜 Victoria\nVIP für 30 Tage: 500 ⭐ statt regulär 1000 ⭐. Gültig für 2 Stunden ab dieser Nachricht. Aktionen können wiederkommen.',
                            'fr': '💜 Victoria\nVIP pour 30 jours : 500 ⭐ au lieu de 1000 ⭐. Offre valable 2 heures après ce message. Elle peut revenir.',
                            'es': '💜 Victoria\nVIP por 30 días: 500 ⭐ en vez de 1000 ⭐. Oferta válida durante 2 horas desde este mensaje. Puede repetirse.',
                        }.get(lg, '')
                    else:
                        copy = t(lg, 'reminder')
                    await bot.send_message(uid, copy,
                        reply_markup=await plans_keyboard(lg, market, bot, uid, deadline))
                    await store.patch(uid, last_reminder_at=now_iso())
                    await store.event(uid, 'simple_reminder_sent')
                    await asyncio.sleep(0.2)
                except TelegramForbiddenError:
                    await store.patch(uid, blocked=True)
                    await store.event(uid, 'simple_reminder_blocked')
                except TelegramRetryAfter as exc:
                    await store.event(uid, 'simple_reminder_rate_limited')
                    await asyncio.sleep(min(float(exc.retry_after) + 0.8, 60))
                except Exception:
                    log.exception('Reminder failure uid=%s', uid)
                    await store.event(uid, 'simple_reminder_failed')
        except Exception:
            log.exception('Reminder loop failed')
        await asyncio.sleep(100)


async def expiry_loop(bot: Bot):
    """Removal only when explicitly enabled after owner tests Bot channel rights."""
    while True:
        await asyncio.sleep(1800)
        if not cfg.remove_expired:
            continue
        try:
            users = await store.all_rows('users',
                'user_id,is_paid,is_premium,premium_until,subscription_tier',
                {'is_premium': 'eq.true', 'premium_until': f'lt.{now_iso()}'}, 10000)
            for u in users:
                if active(u):
                    continue
                uid = int(u['user_id'])
                try:
                    membership = await bot.get_chat_member(cfg.private_id, uid)
                    if str(membership.status) not in ('left', 'kicked'):
                        await bot.ban_chat_member(cfg.private_id, uid)
                        await bot.unban_chat_member(cfg.private_id, uid, only_if_banned=True)
                    await store.patch(uid, is_paid=False, is_premium=False,
                                      subscription_tier='free', sales_stage='expired')
                except Exception:
                    log.exception('Could not remove expired user=%s', uid)
        except Exception:
            log.exception('Expiry loop failed')


async def health(_):
    return web.json_response({'ok': True, 'service': 'victoria-simple', 'mode': 'polling'})


async def main():
    cfg.validate()
    await store.open()
    await store.ping()
    bot = Bot(cfg.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    self_member = await bot.get_chat_member(cfg.private_id, me.id)
    if self_member.status not in ('administrator', 'creator'):
        raise RuntimeError('Bot must be administrator of PRIVATE_CHANNEL_URL')
    if not getattr(self_member, 'can_invite_users', False) and self_member.status != 'creator':
        raise RuntimeError('Bot needs Invite Users permission in private channel')
    if cfg.remove_expired and not getattr(self_member, 'can_restrict_members', False) and self_member.status != 'creator':
        raise RuntimeError('Bot needs Restrict Members permission for expired subscriptions')
    dp = Dispatcher()
    dp.include_router(router)
    # Render web service with UptimeRobot GET /health; no disk or external scheduler.
    app = web.Application()
    app.router.add_get('/health', health)
    app.router.add_get('/', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', cfg.port)
    await site.start()
    log.info('Victoria Simple serving health on port=%s', cfg.port)
    await bot.delete_webhook(drop_pending_updates=False)
    tasks = [asyncio.create_task(reminders_loop(bot)), asyncio.create_task(expiry_loop(bot))]
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await runner.cleanup()
        await store.close()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
