"""Victoria v4: Stars products, private access, persistent inbox and queue."""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import html
import logging
import re
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    ChatJoinRequest,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from catalog import (
    default_market,
    active,
    plans,
    NEW_CODES,
    clean_market,
    new_payload,
    parse_invoice,
    promo_price,
)
from config import cfg
from storage import store, now_iso
from words import LANGS, t, telegram_language
from inbox import InboxMiddleware, current_user
from analytics import detailed_report, chunks

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
# HTTP clients must never log bot token URLs.
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)
log = logging.getLogger("victoria")
router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")
router.message.outer_middleware(InboxMiddleware(store, cfg))
_public_cache = {}
_start_re = re.compile(r"^[a-zA-Z0-9_]{1,48}$")


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def button(text, data=None, url=None):
    return InlineKeyboardButton(text=text, callback_data=data, url=url)


def utc_text(value):
    try:
        return (
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .strftime("%d.%m.%Y %H:%M")
        )
    except (ValueError, TypeError):
        return "—"


def admin(msg):
    return bool(msg.from_user and msg.from_user.id == cfg.admin_id)


def lang_of(u, tg=None):
    return (
        (u or {}).get("lang")
        if (u or {}).get("lang") in LANGS
        else telegram_language(tg) or "en"
    )


async def reg(tg, ref="direct"):
    u = current_user.get()
    return (
        u if u and int(u["user_id"]) == tg.id else await store.upsert_user(tg, ref=ref)
    )


async def admin_alert(bot, text):
    try:
        await bot.send_message(cfg.admin_id, text)
    except Exception:
        log.warning("Admin alert unavailable")


def language_keyboard():
    names = {
        "uk": "Українська",
        "ru": "Русский",
        "en": "English",
        "de": "Deutsch",
        "fr": "Français",
        "es": "Español",
        "pt": "Português",
        "it": "Italiano",
    }
    rows = [
        [button(names[lg], "lang:" + lg) for lg in LANGS[i : i + 2]]
        for i in range(0, len(LANGS), 2)
    ]
    return kb(rows)


def menu(lg, alerts=False):
    return kb(
        [
            [button("💗 " + t(lg, "public_channel"), "menu:public")],
            [
                button(t(lg, "plans"), "menu:plans"),
                button(t(lg, "access"), "menu:access"),
            ],
            [
                button(t(lg, "support"), "menu:support"),
                button(t(lg, "call_button"), "menu:call"),
            ],
            [
                button("🌐 Language", "menu:languages"),
                button("🌍 Region", "menu:regions"),
            ],
        ]
    )


async def public_channel_link(bot, lg):
    entry = cfg.public_for(lg)
    if not entry:
        return None
    cached = _public_cache.get(entry)
    if cached and time.monotonic() < cached[0]:
        return cached[1]
    # Numeric IDs (as on Render) or @usernames create actual join-request links.
    # Existing literal invitation URLs are accepted; their join-request setting is managed in Telegram.
    if entry.startswith(("https://t.me/", "http://t.me/")):
        return entry.replace("http://", "https://", 1)
    chat_id = int(entry) if entry.lstrip("-").isdigit() else entry
    invite = await bot.create_chat_invite_link(
        chat_id,
        name="victoria-blog-" + lg,
        creates_join_request=True,
        expire_date=datetime.now(timezone.utc) + timedelta(days=2),
    )
    url = str(invite.invite_link)
    _public_cache[entry] = (time.monotonic() + 3600, url)
    return url


async def send_gate(msg, bot, u):
    lg = lang_of(u)
    rows = []
    try:
        url = await public_channel_link(bot, lg)
    except Exception:
        url = None
        await admin_alert(
            bot,
            "⚠️ Не удалось создать заявку в блог. Проверь PUB_LINK_"
            + lg.upper()
            + " и право приглашать пользователей.",
        )
    if url:
        rows.append([button(t(lg, "gate_join"), url=url)])
    rows += [
        [button(t(lg, "continue"), "gate:continue")],
        [button("🌐 Language", "menu:languages")],
    ]
    await msg.answer(
        t(lg, "gate") if url else t(lg, "public_unavailable"), reply_markup=kb(rows)
    )


def promo_deadline(u):
    try:
        expiry = datetime.fromisoformat(
            str((u or {}).get("vip_offer_expires_at")).replace("Z", "+00:00")
        )
        return int(expiry.timestamp()) if expiry > datetime.now(timezone.utc) else None
    except (ValueError, TypeError):
        return None


def offer_price(market, code, deadline=None):
    return (
        promo_price(market)
        if code == "daddy" and deadline and deadline > time.time()
        else plans(market)[code].stars
    )


def plans_fallback_keyboard(lg, market, deadline=None):
    return kb(
        [
            [
                button(
                    f"{t(lg, 'button_' + code)} · {offer_price(market, code, deadline)} ⭐",
                    "buy:" + code,
                )
            ]
            for code in NEW_CODES
        ]
    )


async def plans_keyboard(lg, market, bot, user_id, deadline=None):
    # Callback buttons measure actual clicks and don't mint three invoices on every page view.
    return plans_fallback_keyboard(lg, market, deadline)


def summary_text(lg, market="global", variant="A"):
    intro = t(lg, "intro_b" if variant == "B" else "intro")
    descriptions = [
        t(lg, "button_" + c)
        + "\n"
        + t(lg, "invoice_" + c, personal_days=cfg.personal_days, vip_days=cfg.vip_days)
        for c in NEW_CODES
    ]
    return (
        t(lg, "heading")
        + "\n\n"
        + intro
        + "\n\n"
        + "\n\n".join(descriptions)
        + "\n\n"
        + t(lg, "payment_terms")
    )


async def show_plans(msg, bot, u):
    uid = int(u["user_id"])
    lg = lang_of(u)
    market = clean_market(u.get("market"))
    await msg.answer(
        summary_text(lg, market, u.get("experiment_variant", "A")),
        reply_markup=await plans_keyboard(lg, market, bot, uid, promo_deadline(u)),
    )
    await store.patch(uid, last_offer_at=now_iso(), sales_stage="offer_seen")
    await store.event(
        uid, "simple_offer_seen", variant=u.get("experiment_variant", "A")
    )


async def send_home(msg, bot, u):
    if not u.get("onboarding_complete") and not active(u):
        await send_gate(msg, bot, u)
    else:
        await msg.answer(t(lang_of(u), "hello"), reply_markup=menu(lang_of(u)))


@router.message(CommandStart())
async def start(message: Message, bot: Bot):
    if not message.from_user:
        return
    if admin(message):
        return await admin_home(message)
    raw = (message.text or "").split(maxsplit=1)
    ref = raw[1] if len(raw) == 2 and _start_re.fullmatch(raw[1]) else "direct"
    u = await reg(message.from_user, ref)
    await store.rpc("v4_start", p_uid=message.from_user.id)
    await store.event(message.from_user.id, "simple_start", ref=u.get("ref"))
    if not telegram_language(message.from_user.language_code) and not u.get(
        "language_selected"
    ):
        return await message.answer(
            "🌐 Choose your language / Оберіть мову", reply_markup=language_keyboard()
        )
    await send_home(message, bot, u)


@router.callback_query(F.data == "gate:continue")
async def gate_continue(c: CallbackQuery, bot: Bot):
    await c.answer()
    u = await reg(c.from_user)
    u = await store.patch(c.from_user.id, current=u, onboarding_complete=True)
    await store.event(c.from_user.id, "v4_gate_continue")
    # No membership check or automatic blog approval: owner reviews those requests.
    await show_plans(c.message, bot, u)


@router.callback_query(F.data.startswith("lang:"))
async def set_language(c: CallbackQuery, bot: Bot):
    lg = c.data.split(":")[1]
    if lg not in LANGS:
        return await c.answer()
    await c.answer()
    u = await reg(c.from_user)
    u = await store.patch(
        c.from_user.id,
        current=u,
        lang=lg,
        language_selected=True,
        acquisition_lang=u.get("acquisition_lang") or lg,
        market=u.get("market") if u.get("region_confirmed") else default_market(lg),
    )
    await send_home(c.message, bot, u)


@router.callback_query(F.data.startswith("region:"))
async def set_region(c: CallbackQuery, bot: Bot):
    from catalog import MARKETS

    market = c.data.split(":")[1]
    if market not in MARKETS:
        return await c.answer()
    await c.answer()
    u = await reg(c.from_user)
    u = await store.patch(
        c.from_user.id, current=u, market=market, region_confirmed=True
    )
    await show_plans(c.message, bot, u)


@router.callback_query(F.data.startswith("menu:"))
async def open_menu(c: CallbackQuery, bot: Bot):
    await c.answer()
    u = await reg(c.from_user)
    lg = lang_of(u)
    where = c.data.split(":")[1]
    if where == "plans":
        await show_plans(c.message, bot, u)
    elif where == "access":
        await display_access(c.message, bot, u)
    elif where == "support":
        await c.message.answer(t(lg, "ask_support"))
    elif where == "public":
        await send_gate(c.message, bot, u)
    elif where == "languages":
        await c.message.answer("🌐 Language", reply_markup=language_keyboard())
    elif where == "regions":
        from catalog import MARKETS

        await c.message.answer(
            "🌍 Region",
            reply_markup=kb([[button(m.upper(), "region:" + m)] for m in MARKETS]),
        )
    elif where == "call":
        await request_call(c.message, bot, u)
    else:
        await send_home(c.message, bot, u)


@router.message(Command("plans", "buy"))
async def command_plans(msg: Message, bot: Bot):
    await show_plans(msg, bot, await reg(msg.from_user))


@router.message(Command("access"))
async def command_access(msg: Message, bot: Bot):
    await display_access(msg, bot, await reg(msg.from_user))


@router.message(Command("support", "help", "paysupport"))
async def help_command(msg: Message):
    await msg.answer(t(lang_of(await reg(msg.from_user)), "ask_support"))


async def fresh_invite(bot, uid):
    invite = await bot.create_chat_invite_link(
        cfg.private_id,
        name=f"victoria-{uid}"[:32],
        creates_join_request=True,
        expire_date=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    return str(invite.invite_link)


async def display_access(msg, bot, u):
    u = await store.rpc("v4_sync_access", p_uid=int(u["user_id"]))
    lg = lang_of(u)
    uid = int(u["user_id"])
    if not active(u):
        await msg.answer(
            t(lg, "not_paid"),
            reply_markup=await plans_keyboard(
                lg, clean_market(u.get("market")), bot, uid
            ),
        )
        return
    try:
        link = await fresh_invite(bot, uid)
    except Exception:
        await admin_alert(
            bot,
            f"🚨 Инвайт в платный канал недоступен для <code>{uid}</code>. Проверь права бота.",
        )
        await msg.answer(t(lg, "access_error"), reply_markup=menu(lg))
        return
    text = (
        t(lg, "paid")
        + "\n"
        + t(lg, "channel_until")
        + ": "
        + utc_text(u.get("premium_until"))
        + " UTC"
    )
    if u.get("personal_until"):
        text += (
            "\n" + t(lg, "chat_until") + ": " + utc_text(u["personal_until"]) + " UTC"
        )
    if u.get("calls_until"):
        text += "\n" + t(lg, "calls_until") + ": " + utc_text(u["calls_until"]) + " UTC"
    rows = [[button(t(lg, "join"), url=link)]]
    if u.get("personal_until"):
        rows.append([button(t(lg, "support"), "menu:support")])
    if u.get("calls_until"):
        rows.append([button(t(lg, "call_button"), "menu:call")])
    await msg.answer(text, reply_markup=kb(rows))


async def invoice_link(bot, u, code, amount=None, deadline=None):
    lg = lang_of(u)
    market = clean_market(u.get("market"))
    price = amount if amount is not None else offer_price(market, code, deadline)
    payload = new_payload(
        int(u["user_id"]), code, market, promo_until=deadline, custom_amount=amount
    )
    return await bot.create_invoice_link(
        title=t(lg, "invoice_title_" + code)[:32],
        description=t(
            lg,
            "invoice_" + code,
            personal_days=cfg.personal_days,
            vip_days=cfg.vip_days,
        )[:255],
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=t(lg, "button_" + code), amount=price)],
    )


@router.callback_query(F.data.startswith("buy:"))
async def pay(c: CallbackQuery, bot: Bot):
    code = c.data.split(":")[1]
    if code not in NEW_CODES:
        await c.answer("Open current plans", show_alert=True)
        return
    await c.answer()
    u = await reg(c.from_user)
    lg = lang_of(u)
    market = clean_market(u.get("market"))
    deadline = promo_deadline(u) if code == "daddy" else None
    price = offer_price(market, code, deadline)
    await store.event(c.from_user.id, "v4_payment_click", plan=code, stars=price)
    try:
        await bot.send_invoice(
            c.from_user.id,
            title=t(lg, "invoice_title_" + code)[:32],
            description=t(
                lg,
                "invoice_" + code,
                personal_days=cfg.personal_days,
                vip_days=cfg.vip_days,
            )[:255],
            payload=new_payload(c.from_user.id, code, market, promo_until=deadline),
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=t(lg, "button_" + code), amount=price)],
        )
    except Exception:
        await c.message.answer(t(lg, "invoice_error"))
        raise
    await store.patch(
        c.from_user.id, last_checkout_at=now_iso(), sales_stage="checkout_started"
    )
    await admin_alert(
        bot,
        f"⚡ {html.escape(u.get('first_name') or 'User')} · {lg} · <code>{c.from_user.id}</code>\nТариф {code}: {price} ⭐",
    )


@router.pre_checkout_query()
async def confirm_checkout(q: PreCheckoutQuery, bot: Bot):
    d = (
        parse_invoice(q.invoice_payload, q.from_user.id, q.total_amount)
        if q.currency == "XTR"
        else None
    )
    # No DB dependency on the deadline-critical path (Telegram allows 10 seconds).
    await q.answer(
        ok=bool(d),
        error_message=None if d else "Please open a fresh invoice in the bot.",
    )
    if d:
        try:
            await store.upsert_user(q.from_user)
            await store.event(
                q.from_user.id, "simple_checkout", plan=d.code, stars=d.amount
            )
        except Exception:
            log.warning("Optional checkout analytics unavailable")


@router.message(F.successful_payment)
async def confirmed_payment(msg: Message, bot: Bot):
    p = msg.successful_payment
    tg = msg.from_user
    u = await reg(tg)
    d = (
        parse_invoice(p.invoice_payload, tg.id, p.total_amount, allow_expired=True)
        if p.currency == "XTR"
        else None
    )
    if not d:
        # Do not guess what an unknown historical invoice promised. Journal retains the event.
        await admin_alert(
            bot,
            f"🚨 Неизвестный оплаченный счёт. <code>{tg.id}</code> · charge <code>{html.escape(p.telegram_payment_charge_id)}</code>. Нужна ручная сверка условий.",
        )
        raise RuntimeError("Unknown confirmed invoice; retained for review")
    result = await store.rpc(
        "v4_apply_payment",
        p_uid=tg.id,
        p_charge=p.telegram_payment_charge_id,
        p_payload=p.invoice_payload,
        p_amount=p.total_amount,
        p_plan=d.code,
        p_days=d.days,
        p_market=d.market,
    )
    if not result["duplicate"]:
        await admin_alert(
            bot,
            f"💰 <b>Оплата</b> · {html.escape(tg.first_name)} · {lang_of(u)}\nID <code>{tg.id}</code> · {d.code} · {d.amount} ⭐",
        )
    if not result["receipt"].get("refunded_at"):
        await msg.answer(t(lang_of(u), "payment_success"))
        await display_access(msg, bot, result["user"])


@router.message(F.refunded_payment)
async def refund_handler(msg: Message, bot: Bot):
    p = msg.refunded_payment
    u = await store.rpc(
        "v4_refund", p_uid=msg.from_user.id, p_charge=p.telegram_payment_charge_id
    )
    if not active(u):
        await store.req(
            "POST",
            "automation_jobs",
            params={"on_conflict": "dedupe_key"},
            body={
                "user_id": msg.from_user.id,
                "job_type": "v4_revoke",
                "scheduled_at": now_iso(),
                "dedupe_key": "v4:refund-revoke:" + p.telegram_payment_charge_id,
            },
            prefer="resolution=ignore-duplicates,return=minimal",
        )
    await admin_alert(
        bot, f"↩️ Возврат: <code>{msg.from_user.id}</code> · {p.total_amount} ⭐"
    )


@router.chat_join_request()
async def join_request(req: ChatJoinRequest, bot: Bot):
    if req.chat.id == cfg.private_id:
        old = await store.get_user(req.from_user.id)
        if not old:
            return await bot.decline_chat_join_request(req.chat.id, req.from_user.id)
        u = await store.rpc("v4_sync_access", p_uid=req.from_user.id)
        if active(u):
            await bot.approve_chat_join_request(req.chat.id, req.from_user.id)
            await store.patch(req.from_user.id, channel_member=True)
            await store.event(req.from_user.id, "simple_join_approved")
        else:
            await bot.decline_chat_join_request(req.chat.id, req.from_user.id)
    else:
        # The owner's blog is separate. Never auto-approve or reject its requests.
        ids = {
            int(e) for lg in LANGS if (e := cfg.public_for(lg)).lstrip("-").isdigit()
        }
        if req.chat.id in ids:
            u = await reg(req.from_user)
            await store.event(
                req.from_user.id, "v4_blog_request", channel_id=req.chat.id
            )
            await admin_alert(
                bot,
                f"💗 Заявка в блог: {html.escape(req.from_user.first_name)} · {lang_of(u)} · <code>{req.from_user.id}</code>\nОдобри её вручную в Telegram.",
            )


async def request_call(msg, bot, u):
    result = await store.rpc("v4_request_call", p_uid=int(u["user_id"]))
    if not result.get("allowed"):
        return await msg.answer(
            t(lang_of(u), "call_locked"),
            reply_markup=await plans_keyboard(
                lang_of(u), clean_market(u.get("market")), bot, int(u["user_id"])
            ),
        )
    await msg.answer(t(lang_of(u), "call_sent"))
    if result.get("created"):
        await admin_alert(
            bot,
            f"📞 Заявка на звонок #{result['id']}: <code>{u['user_id']}</code> · {lang_of(u)}\n/call_done {result['id']}",
        )


def admin_keyboard():
    return kb(
        [
            [
                button("📊 Статистика", "admin:stats"),
                button("💬 Обращения", "admin:pending"),
            ],
            [
                button("⭐ Платежи", "admin:payments"),
                button("⚙️ Состояние", "admin:metrics"),
            ],
            [
                button("🤝 Партнёры", "admin:partners"),
                button("📞 Звонки", "admin:calls"),
            ],
        ]
    )


@router.message(Command("admin"))
async def admin_home(msg: Message):
    if not admin(msg):
        return
    await msg.answer(
        "💜 <b>Victoria · управление</b>\n/stats · /funnel · /regions · /reminder_stats\n"
        "/pending · /payments · /calls · /metrics\n/user ID · /messages ID · /send ID текст\n"
        "/offer ID secret|mistress|daddy цена текст — подготовить личное предложение\n"
        "/repair — сверить доступы\n/retry_update ID · /retry_job ID — повторить ошибку\n/cancel — закрыть редактор предложения",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data.startswith("admin:"))
async def admin_callback(c: CallbackQuery, bot: Bot):
    if c.from_user.id != cfg.admin_id:
        return await c.answer("Access denied", show_alert=True)
    await c.answer()
    actions = {
        "stats": admin_stats,
        "pending": admin_pending,
        "payments": admin_payments,
        "metrics": admin_metrics,
        "partners": admin_partners,
        "calls": admin_calls,
    }
    fn = actions.get(c.data.split(":")[1])
    if fn:
        await fn(c.message, from_button=True)


@router.message(Command("stats", "funnel", "regions", "reminder_stats"))
async def admin_stats(msg: Message, *, from_button=False):
    if not from_button and not admin(msg):
        return
    for section in await detailed_report(store, cfg):
        await msg.answer(section)


@router.message(Command("metrics"))
async def admin_metrics(msg: Message, *, from_button=False):
    if not from_button and not admin(msg):
        return
    d = await store.rpc("v4_metrics")
    timings = sorted(store.timings)
    lines = [
        "⚙️ <b>Состояние</b>",
        f"Заданий ждёт: {d['jobs_pending']} · ошибочных: {d['jobs_failed']}",
        f"Ошибки Telegram updates: {d['updates_failed']}",
        f"Задержка очереди: {int(d['oldest_job_seconds'])} сек",
        f"Подключений к PostgreSQL (всего в БД): {d['active_connections']}",
        f"Запросы этого процесса p95: {timings[int((len(timings) - 1) * 0.95)] * 1000:.0f} мс"
        if timings
        else "Запросы: нет данных",
    ]
    for r in d.get("tables") or []:
        lines.append(
            f"{html.escape(r['name'])}: ~{r['estimated_rows']} строк · {r['bytes'] / 1048576:.2f} MiB"
        )
    await msg.answer("\n".join(lines))


@router.message(Command("payments"))
async def admin_payments(msg: Message, *, from_button=False):
    if not from_button and not admin(msg):
        return
    rows = await store.req(
        "GET",
        "payments",
        params={
            "select": "id,user_id,amount,plan,created_at,refunded_at",
            "order": "id.desc",
            "limit": "20",
        },
    )
    lines = ["⭐ <b>Последние платежи</b>"] + [
        f"{'↩️' if r.get('refunded_at') else '✅'} #{r['id']} · <code>{r['user_id']}</code> · {html.escape(r['plan'])} · {r['amount']} ⭐"
        for r in rows
    ]
    await msg.answer("\n".join(lines))


@router.message(Command("pending"))
async def admin_pending(msg: Message, *, from_button=False):
    if not from_button and not admin(msg):
        return
    rows = await store.pending()
    lines = ["💬 <b>Ждут ответа · первые 50</b>"]
    for r in rows:
        u = r.get("users") or {}
        lines.append(
            f"{html.escape(u.get('first_name') or 'User')} · {html.escape(u.get('lang') or '?')} · <code>{r['user_id']}</code>\n/user {r['user_id']}"
        )
    for section in chunks(lines):
        await msg.answer(section)


@router.message(Command("user"))
async def admin_user(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await msg.answer("/user ID")
    await user_card(msg, int(parts[1]))


async def user_card(msg, uid):
    u = await store.get_user(uid)
    if not u:
        return await msg.answer("Пользователь не найден")
    payments, ev, messages = await asyncio.gather(
        store.req(
            "GET",
            "payments",
            params={
                "user_id": f"eq.{uid}",
                "select": "amount,plan,created_at,refunded_at",
                "order": "id.desc",
                "limit": "10",
            },
        ),
        store.req(
            "GET",
            "funnel_progress",
            params={"user_id": f"eq.{uid}", "select": "event,hits,first_at,last_at"},
        ),
        store.recent_messages(uid, 5),
    )
    lines = [
        f"👤 <b>{html.escape(u.get('first_name') or 'User')}</b> · <code>{uid}</code>",
        f"🌐 {html.escape(u.get('lang') or '?')} · @{html.escape(u.get('username') or '—')}",
        f"Регистрация: {html.escape(str(u.get('created_at'))[:16])} UTC",
        f"Источник: {html.escape(u.get('ref') or 'direct')} · A/B: {html.escape(u.get('experiment_variant') or 'legacy')}",
        f"Тариф: {html.escape(u.get('subscription_tier') or 'free')} · до {html.escape(str(u.get('premium_until') or '—'))[:25]}",
        "<b>Этапы</b>",
    ]
    lines += [
        f"{html.escape(r['event'])}: {r['hits']} · {str(r['last_at'])[:16]}" for r in ev
    ]
    lines += ["<b>Последние платежи</b>"] + [
        f"{r['amount']} ⭐ · {html.escape(r['plan'])} · {'возврат' if r.get('refunded_at') else 'оплачен'}"
        for r in payments
    ]
    lines += ["<b>Последние сообщения</b>"] + [
        html.escape(r["role"] + ": " + r["content"][:300]) for r in reversed(messages)
    ]
    for section in chunks(lines):
        await msg.answer(section)
    await msg.answer(
        "Действия",
        reply_markup=kb(
            [
                [button("✍️ Текст + кнопка оплаты", f"offeruser:{uid}")],
                [button("💬 История", f"history:{uid}:0:0")],
            ]
        ),
    )


@router.message(Command("messages"))
async def admin_messages(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or "").split()
    if (
        len(parts) not in (2, 3)
        or not parts[1].isdigit()
        or (len(parts) == 3 and not parts[2].isdigit())
    ):
        return await msg.answer("/messages ID [страница]")
    await history_page(
        msg, int(parts[1]), max(0, int(parts[2]) - 1) if len(parts) == 3 else 0
    )


async def history_page(msg, uid, page=0, archived=False):
    rows = await store.recent_messages(uid, 20, offset=page * 20, archived=archived)
    await msg.answer(
        f"💬 История · {uid} · страница {page + 1}" + (" · архив" if archived else "")
    )
    for r in reversed(rows):
        text = r["role"] + " · " + utc_text(r["created_at"]) + " UTC\n" + r["content"]
        for i in range(0, len(text), 3500):
            await msg.answer(text[i : i + 3500], parse_mode=None)
    controls = []
    if page > 0:
        controls.append(button("← Новее", f"history:{uid}:{page - 1}:{int(archived)}"))
    if len(rows) == 20:
        controls.append(button("Старее →", f"history:{uid}:{page + 1}:{int(archived)}"))
    board = [controls] if controls else []
    board.append(
        [
            button(
                "Текущая история" if archived else "Архив старше 180 дней",
                f"history:{uid}:0:{int(not archived)}",
            )
        ]
    )
    await msg.answer(
        "Навигация" if rows else "Сообщений на этой странице нет.",
        reply_markup=kb(board),
    )


@router.callback_query(F.data.startswith("history:"))
async def history_callback(c: CallbackQuery):
    if c.from_user.id != cfg.admin_id:
        return await c.answer("Access denied", show_alert=True)
    await c.answer()
    _, uid, page, archived = c.data.split(":")
    await history_page(c.message, int(uid), max(0, int(page)), archived == "1")


@router.message(Command("send", "reply"))
async def admin_send(msg: Message, bot: Bot):
    if not admin(msg):
        return
    parts = (msg.text or "").split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        return await msg.answer("/send ID текст")
    uid = int(parts[1])
    text = parts[2]
    if not await store.get_user(uid):
        return await msg.answer("Нет такого пользователя")
    waiting = await store.req(
        "GET",
        "pending_replies",
        params={"user_id": f"eq.{uid}", "select": "updated_at", "limit": "1"},
    )
    await bot.send_message(uid, text, parse_mode=None)
    await store.message(uid, "assistant", text)
    await store.patch(uid, last_admin_reply_at=now_iso())
    await store.ticket_closed(uid, waiting[0]["updated_at"] if waiting else None)
    await msg.answer("✅ Ответ отправлен.")


@router.message(Command("repair"))
async def admin_repair(msg: Message):
    if admin(msg):
        await msg.answer(f"✅ Доступы сверены: {await store.restore_receipts()}")


@router.message(Command("retry_update", "retry_job"))
async def retry_failed(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await msg.answer("/retry_update ID или /retry_job ID")
    table = "telegram_updates" if "retry_update" in parts[0] else "automation_jobs"
    key = "update_id" if table == "telegram_updates" else "id"
    body = {
        "status": "pending",
        "attempts": 0,
        "locked_at": None,
        "locked_by": None,
        "last_error": None,
        "available_at" if table == "telegram_updates" else "scheduled_at": now_iso(),
    }
    await store.req(
        "PATCH",
        table,
        params={key: "eq." + parts[1], "status": "eq.failed"},
        body=body,
        prefer="return=minimal",
    )
    await msg.answer("✅ Повтор поставлен в очередь, если запись была в failed.")


@router.message(Command("calls"))
async def admin_calls(msg: Message, *, from_button=False):
    if not from_button and not admin(msg):
        return
    rows = await store.req(
        "GET",
        "call_requests",
        params={
            "status": "eq.pending",
            "select": "id,user_id,created_at",
            "order": "id.asc",
            "limit": "30",
        },
    )
    await msg.answer(
        "📞 <b>Звонки</b>\n"
        + (
            "\n".join(
                f"#{r['id']} · <code>{r['user_id']}</code> · /call_done {r['id']}"
                for r in rows
            )
            or "Нет заявок"
        )
    )


@router.message(Command("call_done"))
async def call_done(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await msg.answer("/call_done ID")
    await store.req(
        "PATCH",
        "call_requests",
        params={"id": "eq." + parts[1]},
        body={"status": "completed"},
        prefer="return=minimal",
    )
    await msg.answer("✅ Звонок отмечен выполненным.")


# ---------- Traffic partners ----------
@router.message(Command("partners"))
async def admin_partners(msg: Message, *, from_button: bool = False):
    if not from_button and not admin(msg):
        return
    partners = await store.rpc("v4_partners")
    username = (await msg.bot.get_me()).username
    lines = ["🤝 <b>Партнёры</b>"]
    for p in partners:
        lines.append(
            f"\n<b>{html.escape(p['display_name'])}</b> ({html.escape(p['code'])})"
            f"\nПривёл: {p['users']} · покупок: {p['purchases']}"
            f"\nНачислено: {p['earned']} ⭐ · выплачено: {p['paid']} ⭐ · остаток: {p['earned'] - p['paid']} ⭐"
            f"\nСтавка: {p['commission_pct']}% · {'активен' if p['active'] else 'выключен'}"
            f"\nhttps://t.me/{username}?start={p['code']}"
        )
    lines.append(
        "\n/addpartner ID код название — добавить (30%)"
        "\n/partnerpct код процент — изменить ставку"
        "\n/partneroff код — выключить; /partneron код — включить"
        "\n/partnerpay код сумма — записать выплату в Stars"
    )
    for section in chunks(lines):
        await msg.answer(section, disable_web_page_preview=True)


@router.message(Command("addpartner"))
async def add_partner(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or "").split(maxsplit=3)
    if (
        len(parts) < 4
        or not parts[1].isdigit()
        or not re.fullmatch(r"[a-z0-9_]{3,32}", parts[2])
    ):
        await msg.answer("Формат: /addpartner TELEGRAM_ID code Имя")
        return
    try:
        await store.req(
            "POST",
            "traffic_partners",
            body={
                "telegram_user_id": int(parts[1]),
                "code": parts[2],
                "display_name": parts[3],
                "commission_pct": 30,
            },
            prefer="return=minimal",
        )
        await msg.answer("✅ Заливщик добавлен. /partners")
    except Exception as exc:
        await msg.answer("Ошибка добавления: " + html.escape(str(exc)[:200]))


@router.message(Command("partnerpct", "partneroff", "partneron", "partnerpay"))
async def partner_manage(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or "").split()
    cmd = parts[0].split("@")[0].lstrip("/")
    if len(parts) != (3 if cmd in ("partnerpct", "partnerpay") else 2):
        await msg.answer("Неверные аргументы. См. /partners")
        return
    rows = await store.req(
        "GET",
        "traffic_partners",
        params={"code": "eq." + parts[1], "select": "*", "limit": "1"},
    )
    if not rows:
        await msg.answer("Код не найден")
        return
    partner = rows[0]
    if cmd in ("partneroff", "partneron"):
        await store.req(
            "PATCH",
            "traffic_partners",
            params={"id": "eq." + str(partner["id"])},
            body={"active": cmd == "partneron"},
            prefer="return=minimal",
        )
    elif cmd == "partnerpct":
        try:
            rate = float(parts[2])
            assert 0 <= rate <= 100
        except (ValueError, AssertionError):
            await msg.answer("Процент должен быть 0–100")
            return
        await store.req(
            "PATCH",
            "traffic_partners",
            params={"id": "eq." + str(partner["id"])},
            body={"commission_pct": rate},
            prefer="return=minimal",
        )
    else:
        try:
            amount = int(parts[2])
            assert amount > 0
        except (ValueError, AssertionError):
            await msg.answer("Сумма должна быть положительной")
            return
        await store.req(
            "POST",
            "partner_payouts",
            body={
                "partner_id": partner["id"],
                "amount_stars": amount,
                "note": "Manual admin record",
            },
            prefer="return=minimal",
        )
    await msg.answer("✅ Сохранено. /partners")


# ---------- Persistent manual offer composer ----------
async def get_draft():
    rows = await store.req(
        "GET",
        "manual_offer_drafts",
        params={
            "admin_id": f"eq.{cfg.admin_id}",
            "expires_at": "gt." + now_iso(),
            "select": "*",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


async def save_draft(uid, **fields):
    await store.req(
        "POST",
        "manual_offer_drafts",
        params={"on_conflict": "admin_id"},
        body={
            "admin_id": cfg.admin_id,
            "user_id": uid,
            "plan": None,
            "amount": None,
            "body": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            **fields,
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


async def preview_offer(msg, draft):
    u = await store.get_user(int(draft["user_id"]))
    lg = lang_of(u)
    if not draft.get("plan"):
        return await msg.answer(
            "Выбери тариф для кнопки:",
            reply_markup=kb(
                [[button(t(lg, "button_" + c), "offerplan:" + c)] for c in NEW_CODES]
            ),
        )
    code = draft["plan"]
    await msg.answer(
        f"👀 <b>Предпросмотр для {html.escape(u.get('first_name') or 'User')}</b> · {lg}\n\n"
        + html.escape(draft["body"])
        + f"\n\n[{t(lg, 'button_' + code)} · {draft['amount']} ⭐]",
        reply_markup=kb(
            [
                [button("✅ Отправить", "offer:send"), button("Цена", "offer:price")],
                [button("Отмена", "offer:cancel")],
            ]
        ),
    )


@router.message(Command("offer"))
async def command_offer(msg: Message):
    if not admin(msg):
        return
    parts = (msg.text or "").split(maxsplit=4)
    if (
        len(parts) != 5
        or not parts[1].isdigit()
        or parts[2] not in NEW_CODES
        or not parts[3].isdigit()
        or not 1 <= int(parts[3]) <= 10000
    ):
        return await msg.answer("/offer ID secret|mistress|daddy цена_Stars текст")
    if not await store.get_user(int(parts[1])):
        return await msg.answer("Пользователь не найден")
    if len(parts[4]) > 3000:
        return await msg.answer("Текст до 3000 символов.")
    await save_draft(int(parts[1]), plan=parts[2], amount=int(parts[3]), body=parts[4])
    await preview_offer(msg, await get_draft())


@router.callback_query(F.data.startswith("offeruser:"))
async def begin_offer(c: CallbackQuery):
    if c.from_user.id != cfg.admin_id:
        return await c.answer("Access denied", show_alert=True)
    await c.answer()
    uid = int(c.data.split(":")[1])
    await save_draft(uid)
    await c.message.answer(
        "Напиши текст личного предложения следующим сообщением. /cancel — отменить."
    )


@router.callback_query(F.data.startswith("offerplan:"))
async def choose_offer_plan(c: CallbackQuery):
    if c.from_user.id != cfg.admin_id:
        return await c.answer("Access denied", show_alert=True)
    await c.answer()
    draft = await get_draft()
    code = c.data.split(":")[1]
    if not draft or not draft.get("body") or code not in NEW_CODES:
        return
    u = await store.get_user(int(draft["user_id"]))
    draft.update(plan=code, amount=plans(clean_market(u.get("market")))[code].stars)
    await save_draft(
        int(draft["user_id"]), plan=code, amount=draft["amount"], body=draft["body"]
    )
    await preview_offer(c.message, draft)


@router.callback_query(F.data.startswith("offer:"))
async def offer_action(c: CallbackQuery, bot: Bot):
    if c.from_user.id != cfg.admin_id:
        return await c.answer("Access denied", show_alert=True)
    await c.answer()
    draft = await get_draft()
    action = c.data.split(":")[1]
    if action == "cancel":
        await store.req(
            "DELETE",
            "manual_offer_drafts",
            params={"admin_id": f"eq.{cfg.admin_id}"},
            prefer="return=minimal",
        )
        return await c.message.answer("Отменено.")
    if not draft or not draft.get("plan"):
        return await c.message.answer(
            "Черновик истёк. Открой карточку пользователя ещё раз."
        )
    if action == "price":
        await store.req(
            "PATCH",
            "manual_offer_drafts",
            params={"admin_id": f"eq.{cfg.admin_id}"},
            body={"amount": None},
            prefer="return=minimal",
        )
        return await c.message.answer(
            "Отправь новую цену целым числом в Stars (1–10000)."
        )
    if action == "send" and draft.get("amount"):
        u = await store.get_user(int(draft["user_id"]))
        link = await invoice_link(bot, u, draft["plan"], amount=int(draft["amount"]))
        label = f"{t(lang_of(u), 'button_' + draft['plan'])} · {draft['amount']} ⭐"
        await bot.send_message(
            int(u["user_id"]),
            draft["body"],
            parse_mode=None,
            reply_markup=kb([[button(label, url=link)]]),
        )
        await store.message(
            int(u["user_id"]), "assistant", draft["body"] + "\n[" + label + "]"
        )
        await store.event(
            int(u["user_id"]),
            "v4_manual_offer",
            plan=draft["plan"],
            stars=draft["amount"],
        )
        await store.req(
            "DELETE",
            "manual_offer_drafts",
            params={"admin_id": f"eq.{cfg.admin_id}"},
            prefer="return=minimal",
        )
        await c.message.answer("✅ Предложение отправлено: текст и одна кнопка оплаты.")


@router.message(Command("cancel"))
async def cancel_draft(msg: Message):
    if admin(msg):
        await store.req(
            "DELETE",
            "manual_offer_drafts",
            params={"admin_id": f"eq.{cfg.admin_id}"},
            prefer="return=minimal",
        )
        await msg.answer("Редактор закрыт.")


@router.message()
async def user_message(msg: Message, bot: Bot):
    if not msg.from_user:
        return
    if admin(msg):
        draft = await get_draft()
        if not draft:
            return
        text = msg.text or ""
        if draft.get("plan") and draft.get("amount") is None:
            if not text.isdigit() or not 1 <= int(text) <= 10000:
                return await msg.answer("Нужно число от 1 до 10000.")
            draft["amount"] = int(text)
        else:
            if not text or len(text) > 3000:
                return await msg.answer("Пришли текст до 3000 символов.")
            draft["body"] = text
        await save_draft(
            int(draft["user_id"]),
            plan=draft.get("plan"),
            amount=draft.get("amount"),
            body=draft.get("body"),
        )
        return await preview_offer(msg, draft)
    u = await reg(msg.from_user)
    await msg.answer(t(lang_of(u), "support_received"))


async def health(_):
    from workers import runtime_state

    stale = any(
        time.monotonic() - runtime_state.get(name, 0) > 90
        for name in ("poll", "updates", "scheduler")
    )
    return web.json_response(
        {"ok": not stale, "service": "victoria-v4"}, status=503 if stale else 200
    )


async def main():
    cfg.validate()
    await store.open()
    await store.ping()
    bot = Bot(cfg.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    me = await bot.get_me()
    member = await bot.get_chat_member(cfg.private_id, me.id)
    if member.status not in ("administrator", "creator"):
        raise RuntimeError("Bot must administer private channel")
    for permission in (
        "can_invite_users",
        *(["can_restrict_members"] if cfg.remove_expired else []),
    ):
        if member.status != "creator" and not getattr(member, permission, False):
            raise RuntimeError("Missing channel permission: " + permission)
    dp = Dispatcher()
    dp.include_router(router)
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", cfg.port).start()
    from workers import (
        durable_poll,
        update_worker,
        automation_worker,
        scheduler,
        expiry_worker,
    )

    await bot.delete_webhook(drop_pending_updates=False)
    tasks = [
        asyncio.create_task(durable_poll(bot, dp)),
        asyncio.create_task(update_worker(bot, dp)),
        asyncio.create_task(automation_worker(bot)),
        asyncio.create_task(scheduler(bot)),
        asyncio.create_task(expiry_worker(bot)),
    ]
    try:
        # A dead worker must terminate the service for Render to restart it.
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await runner.cleanup()
        await store.close()
        await bot.session.close()


if __name__ == "__main__":
    import sys

    sys.modules["main"] = sys.modules[__name__]
    asyncio.run(main())
