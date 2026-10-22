"""Persistent work scheduling and Telegram update journal.

Telegram sends have at-least-once delivery: a crash after Telegram accepts a send
but before DB acknowledgement can repeat it. Financial effects are transactional
and idempotent by Telegram charge ID, including concurrent delivery.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import html
import logging
import time
import uuid
import weakref
from aiogram.types import Update
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from catalog import active, clean_market, plans, promo_price
from config import cfg
from storage import store, now_iso
from words import t

log = logging.getLogger(__name__)
runtime_state = {"poll": time.monotonic(), "scheduler": time.monotonic()}
_locks = weakref.WeakValueDictionary()
updates_ready = asyncio.Event()
jobs_ready = asyncio.Event()


def user_lock(uid):
    lock = _locks.get(uid)
    if lock is None:
        lock = asyncio.Lock()
        _locks[uid] = lock
    return lock


def update_uid(body):
    for key in ("message", "callback_query", "chat_join_request", "pre_checkout_query"):
        item = body.get(key) or {}
        uid = (item.get("from") or {}).get("id")
        if uid:
            return int(uid)
    return int(body["update_id"])


async def durable_poll(bot, dp):
    """Confirm getUpdates offsets only after ordinary updates are durably stored."""
    offset = None
    while True:
        try:
            batch = await bot.get_updates(
                offset=offset,
                timeout=25,
                limit=100,
                allowed_updates=dp.resolve_used_update_types(),
            )
            runtime_state["poll"] = time.monotonic()
            if not batch:
                continue
            # Pre-checkout must be answered within 10 seconds, ahead of persistence.
            for update in batch:
                if update.pre_checkout_query:
                    try:
                        await dp.feed_update(bot, update)
                    except Exception:
                        log.warning(
                            "Pre-checkout response failed or query already expired"
                        )
            bodies = [
                {
                    "update_id": u.update_id,
                    "body": u.model_dump(mode="json", exclude_none=True),
                    "status": "done" if u.pre_checkout_query else "pending",
                }
                for u in batch
            ]
            await store.req(
                "POST",
                "telegram_updates",
                params={"on_conflict": "update_id"},
                body=bodies,
                prefer="resolution=ignore-duplicates,return=minimal",
            )
            updates_ready.set()
            offset = max(u.update_id for u in batch) + 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(min(float(exc.retry_after) + 0.3, 60))
        except Exception:
            log.warning("Polling or update persistence unavailable; offset retained")
            await asyncio.sleep(2)


async def finish(table, key, value, worker, *, status="done", delay=0, error=None):
    body = {"status": status, "locked_at": None, "locked_by": None, "last_error": error}
    if status == "pending":
        body["available_at" if table == "telegram_updates" else "scheduled_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=delay)
        ).isoformat()
    if status == "sent":
        body["sent_at"] = now_iso()
    await store.req(
        "PATCH",
        table,
        params={
            key: f"eq.{value}",
            "locked_by": "eq." + worker,
            "status": "eq.processing",
        },
        body=body,
        prefer="return=minimal",
    )


async def update_worker(bot, dp):
    worker = "updates-" + uuid.uuid4().hex
    from main import admin_alert

    async def dispatch(row):
        body = row["body"]
        uid = update_uid(body)
        try:
            async with user_lock(uid):
                await asyncio.wait_for(
                    dp.feed_update(
                        bot, Update.model_validate(body, context={"bot": bot})
                    ),
                    timeout=180,
                )
            await finish("telegram_updates", "update_id", row["update_id"], worker)
        except Exception as exc:
            # Store class names only: exception strings may contain tokens or customer text.
            if (body.get("message") or {}).get("successful_payment") and int(
                row["attempts"]
            ) == 1:
                await admin_alert(
                    bot,
                    f"🚨 Telegram подтвердил оплату пользователя <code>{uid}</code>, обработка задержана. Update <code>{row['update_id']}</code> сохранён и будет повторён автоматически.",
                )
            exhausted = int(row["attempts"]) >= 8
            await finish(
                "telegram_updates",
                "update_id",
                row["update_id"],
                worker,
                status="failed" if exhausted else "pending",
                delay=(
                    float(exc.retry_after) + 1
                    if isinstance(exc, TelegramRetryAfter)
                    else min(300, 2 ** int(row["attempts"]))
                ),
                error=type(exc).__name__,
            )
            if exhausted:
                await admin_alert(
                    bot,
                    f"🚨 Update <code>{row['update_id']}</code> не обработан. Пользователь <code>{uid}</code>. Проверь /metrics и логи; /retry_update {row['update_id']}",
                )
            log.warning(
                "Update failed id=%s class=%s", row["update_id"], type(exc).__name__
            )

    while True:
        try:
            updates_ready.clear()
            rows = await store.rpc("v4_claim_updates", p_worker=worker, p_limit=4)
            runtime_state["updates"] = time.monotonic()
            if not rows:
                try:
                    await asyncio.wait_for(updates_ready.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass
                continue
            await asyncio.gather(
                *(dispatch(r) for r in sorted(rows, key=lambda r: r["update_id"]))
            )
        except Exception:
            log.warning("Update worker DB unavailable")
            await asyncio.sleep(3)


async def send_job(bot, job):
    from main import lang_of, invoice_link, kb, button, menu

    uid = int(job["user_id"])
    u = await store.get_user(uid)
    kind = job["job_type"]
    if kind == "v4_revoke":
        u = await store.rpc("v4_sync_access", p_uid=uid)
        if active(u):
            return False
        if cfg.remove_expired:
            await bot.ban_chat_member(cfg.private_id, uid)
            await bot.unban_chat_member(cfg.private_id, uid, only_if_banned=True)
        await store.patch(uid, channel_member=False, sales_stage="expired")
        return True
    if not u or u.get("blocked") or u.get("automation_paused"):
        return False
    lg = lang_of(u)
    name = html.escape(u.get("first_name") or "💗")
    if kind == "v4_followup":
        # Choice is deterministic across retries, not a new random message after a restart.
        index = uid % 4
        await bot.send_message(uid, t(lg, "followup_" + str(index), name=name))
        await store.event(uid, "v4_followup_sent")
    elif kind == "v4_daily":
        if active(u):
            await bot.send_message(
                uid,
                t(
                    lg,
                    "followup_" + str((uid + datetime.now(timezone.utc).day) % 4),
                    name=name,
                ),
                reply_markup=menu(lg),
            )
        else:
            market = clean_market(u.get("market"))
            regular = plans(market)["daddy"].stars
            # Fixed to this queued offer. A retry never extends its discount window.
            expiry = (job.get("payload") or {}).get("offer_until")
            if not expiry:
                expiry = int(time.time()) + 7200
                await store.req(
                    "PATCH",
                    "automation_jobs",
                    params={"id": f"eq.{job['id']}"},
                    body={
                        "payload": {**(job.get("payload") or {}), "offer_until": expiry}
                    },
                    prefer="return=minimal",
                )
            if expiry <= time.time():
                return False
            await store.patch(
                uid,
                vip_offer_expires_at=datetime.fromtimestamp(
                    expiry, timezone.utc
                ).isoformat(),
            )
            if regular > 1:
                link = await invoice_link(bot, u, "daddy", deadline=expiry)
                text = (
                    t(lg, "vip_offer")
                    + "\n\n"
                    + t(
                        lg,
                        "vip_terms",
                        until=datetime.fromtimestamp(expiry, timezone.utc).strftime(
                            "%d.%m %H:%M"
                        ),
                        price=promo_price(market),
                        regular=regular,
                    )
                )
                board = kb(
                    [
                        [
                            button(
                                f"{t(lg, 'button_daddy')} · {promo_price(market)} ⭐",
                                url=link,
                            )
                        ]
                    ]
                )
            else:
                # No fictitious discount if the configured regular price is already 1 Star.
                link = await invoice_link(bot, u, "daddy")
                text = t(lg, "invoice_daddy", vip_days=cfg.vip_days)
                board = kb(
                    [[button(f"{t(lg, 'button_daddy')} · {regular} ⭐", url=link)]]
                )
            await bot.send_message(uid, text, reply_markup=board)
            await store.event(uid, "v4_vip_offer_sent", stars=promo_price(market))
        await store.patch(uid, last_reminder_at=now_iso())
        await store.event(uid, "simple_reminder_sent")
    elif kind == "v4_expiry_notice":
        data = job.get("payload") or {}
        source = data.get("source")
        grants = await store.req(
            "GET",
            "access_grants",
            params={
                "source": "eq." + str(source),
                "revoked_at": "is.null",
                "ends_at": "gt." + now_iso(),
                "select": "tier,ends_at",
                "limit": "1",
            },
        )
        if not grants:
            return False
        tier = grants[0]["tier"]
        code = (
            tier
            if tier in plans()
            else {"trial": "secret", "forever": "secret", "vip": "daddy"}.get(
                tier, "secret"
            )
        )
        # Skip obsolete notices when the same tier was already renewed beyond this grant.
        later = await store.req(
            "GET",
            "access_grants",
            params={
                "user_id": f"eq.{uid}",
                "tier": "eq." + tier,
                "revoked_at": "is.null",
                "ends_at": "gt." + str(grants[0]["ends_at"]),
                "select": "source",
                "limit": "1",
            },
        )
        if later:
            return False
        until = (
            datetime.fromisoformat(grants[0]["ends_at"].replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .strftime("%d.%m %H:%M")
        )
        await bot.send_message(
            uid,
            t(lg, "expiry", until=until),
            reply_markup=kb([[button(t(lg, "button_" + code), "buy:" + code)]]),
        )
        await store.event(uid, "v4_subscription_notice")
    else:
        return False
    return True


async def automation_worker(bot):
    from main import admin_alert

    worker = "jobs-" + uuid.uuid4().hex
    while True:
        try:
            # Small batches ensure lease times exceed worst-case API processing time.
            jobs_ready.clear()
            jobs = await store.rpc(
                "v4_claim_jobs",
                p_worker=worker,
                p_limit=1,
                p_notifications=cfg.followups,
            )
            if not jobs:
                try:
                    await asyncio.wait_for(jobs_ready.wait(), timeout=20)
                except asyncio.TimeoutError:
                    pass
                continue
            for job in jobs:
                uid = int(job["user_id"])
                try:
                    async with user_lock(uid):
                        sent = await asyncio.wait_for(send_job(bot, job), timeout=120)
                    await finish(
                        "automation_jobs",
                        "id",
                        job["id"],
                        worker,
                        status="sent" if sent else "cancelled",
                    )
                    await asyncio.sleep(0.15)
                except TelegramForbiddenError:
                    if job["job_type"] == "v4_revoke":
                        await finish(
                            "automation_jobs",
                            "id",
                            job["id"],
                            worker,
                            status="pending",
                            delay=600,
                            error="ChannelPermissions",
                        )
                        await admin_alert(
                            bot,
                            "🚨 Бот не может удалить истёкший доступ. Проверь право блокировать участников в приватном канале.",
                        )
                        continue
                    await store.patch(uid, blocked=True)
                    await finish(
                        "automation_jobs",
                        "id",
                        job["id"],
                        worker,
                        status="cancelled",
                        error="TelegramForbiddenError",
                    )
                except TelegramRetryAfter as exc:
                    # Respect full retry_after in persisted due time; never retry early after restart.
                    await finish(
                        "automation_jobs",
                        "id",
                        job["id"],
                        worker,
                        status="pending",
                        delay=float(exc.retry_after) + 1,
                        error="TelegramRetryAfter",
                    )
                    await asyncio.sleep(min(float(exc.retry_after) + 1, 60))
                except Exception as exc:
                    exhausted = int(job["attempts"]) >= 8
                    await finish(
                        "automation_jobs",
                        "id",
                        job["id"],
                        worker,
                        status="failed" if exhausted else "pending",
                        delay=min(600, 2 ** int(job["attempts"])),
                        error=type(exc).__name__,
                    )
                    if exhausted:
                        await admin_alert(
                            bot,
                            f"🚨 Задание #{job['id']} не выполнено. /retry_job {job['id']}",
                        )
        except Exception:
            log.warning("Automation worker unavailable")
            await asyncio.sleep(3)


async def scheduler(bot):
    last_cleanup = 0
    while True:
        try:
            clock = cfg.reminder_time
            if cfg.followups:
                scheduled = await store.rpc(
                    "v4_schedule",
                    p_tz=cfg.reminder_timezone,
                    p_clock=clock,
                    p_admin=cfg.admin_id,
                )
                if scheduled:
                    jobs_ready.set()
            if time.monotonic() - last_cleanup > 3600:
                await store.rpc("v4_cleanup")
                last_cleanup = time.monotonic()
            runtime_state["scheduler"] = time.monotonic()
        except Exception:
            log.warning("Scheduler unavailable")
        await asyncio.sleep(20)


async def expiry_worker(bot):
    while True:
        try:
            grants = await store.req(
                "GET",
                "access_grants",
                params={
                    "revoked_at": "is.null",
                    "expired_processed_at": "is.null",
                    "ends_at": "lte." + now_iso(),
                    "select": "user_id,source,ends_at",
                    "order": "ends_at.asc",
                    "limit": "100",
                },
            )
            seen = set()
            for row in grants:
                uid = int(row["user_id"])
                if uid in seen:
                    continue
                seen.add(uid)
                async with user_lock(uid):
                    await store.req(
                        "POST",
                        "automation_jobs",
                        params={"on_conflict": "dedupe_key"},
                        body={
                            "user_id": uid,
                            "job_type": "v4_revoke",
                            "scheduled_at": now_iso(),
                            "dedupe_key": "v4:grant-expiry:" + str(row["source"]),
                        },
                        prefer="resolution=ignore-duplicates,return=minimal",
                    )
                    await store.rpc("v4_sync_access", p_uid=uid)
                    jobs_ready.set()
                    await store.req(
                        "PATCH",
                        "access_grants",
                        params={
                            "user_id": f"eq.{uid}",
                            "ends_at": "lte." + now_iso(),
                            "expired_processed_at": "is.null",
                        },
                        body={"expired_processed_at": now_iso()},
                        prefer="return=minimal",
                    )
        except Exception:
            log.warning("Expiry reconciliation failed; will retry")
        await asyncio.sleep(60)
