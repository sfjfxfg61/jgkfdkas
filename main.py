from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timedelta, timezone

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError

import keyboards
from config import settings
from database import DatabaseError, store
from handlers import _public_membership, remove_channel_access, router
from middlewares import SlidingWindowRateLimit
from reply_ai import reply_ai
from sales_copy import followup_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)
WORKER_ID = (os.getenv("RENDER_INSTANCE_ID") or os.getenv("RENDER_SERVICE_ID") or socket.gethostname() or "victoria-worker")[:120]
_system_alerts: dict[str, datetime] = {}


async def _system_alert(bot: Bot, key: str, text: str, *, cooldown_minutes: int = 15) -> None:
    """Best-effort admin alert with a cooldown so broken workers do not spam."""
    if not settings.admin_id:
        return
    now = datetime.now(timezone.utc)
    last = _system_alerts.get(key)
    if last and now - last < timedelta(minutes=cooldown_minutes):
        return
    _system_alerts[key] = now
    try:
        await bot.send_message(settings.admin_id, text)
    except Exception:
        logger.exception("Could not send system alert %s", key)



def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def health(_: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "service": "victoria-personal-bot",
        "mode": "manual-first",
        "auto_reply_ai": settings.auto_reply_ai,
        "followups_enabled": settings.followups_enabled,
    })


async def channel_expiry_loop(bot: Bot) -> None:
    if not settings.private_channel_ref:
        logger.warning("PRIVATE_CHANNEL_URL/ID is not resolvable; private-channel expiry worker disabled")
        return
    while True:
        try:
            for row in await store.expired_members():
                user_id = int(row["user_id"])
                current = await store.get_user(user_id)
                expires = _parse_time((current or {}).get("premium_until"))
                if current and current.get("is_premium") and expires and expires > datetime.now(timezone.utc):
                    continue
                try:
                    await remove_channel_access(bot, user_id)
                except Exception:
                    logger.exception("Could not remove expired private-channel member %s", user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Private-channel expiry loop failed")
        await asyncio.sleep(300)


async def global_reactivation_seed_loop(bot: Bot) -> None:
    """Keep a durable daily reminder alive for every reachable free user.

    This is intentionally broader than paywall/checkout follow-ups: users who have
    never opened the offer are also reactivated. Existing users are staggered over
    roughly one hour so a deploy does not blast the whole database at once.
    """
    if not settings.followups_enabled:
        return
    await asyncio.sleep(20)
    while True:
        try:
            now = datetime.now(timezone.utc)
            offset = 0
            seeded = 0
            while True:
                rows = await store.reactivation_candidates(limit=1000, offset=offset)
                if not rows:
                    break
                for user in rows:
                    user_id = int(user["user_id"])
                    stage = str(user.get("sales_stage") or "new")
                    # Once someone opened the offer/checkout, the more specific
                    # offer_daily/checkout_daily chain takes over instead.
                    if stage not in {"new", "channel_required", "channel_joined", "engaged"}:
                        continue
                    created = _parse_time(user.get("created_at"))
                    if created and now - created < timedelta(hours=48):
                        # New users already receive the 6h -> 24h -> 48h sequence.
                        continue
                    jitter_minutes = 5 + (user_id % 56)
                    when = now + timedelta(minutes=jitter_minutes)
                    payload = {
                        "origin_at": now.isoformat(),
                        "day": now.date().toordinal(),
                        "seed": "global-reactivation",
                    }
                    await store.schedule_job(
                        user_id,
                        "cold_daily",
                        when.isoformat(),
                        f"cold:{user_id}:{when.date().isoformat()}",
                        payload,
                    )
                    seeded += 1
                if len(rows) < 1000:
                    break
                offset += len(rows)
            logger.info("Global reactivation seed pass complete: %s candidate jobs", seeded)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Global reactivation seeder failed")
            await _system_alert(
                bot,
                "reactivation-seed-error",
                f"⚠️ <b>Не удалось засеять глобальные напоминания</b>\n<code>{str(exc)[:700]}</code>",
            )
        # Re-seed several times a day. Stable daily dedupe keys prevent duplicates.
        await asyncio.sleep(6 * 60 * 60)


async def followup_loop(bot: Bot) -> None:
    if not settings.followups_enabled:
        return
    await asyncio.sleep(8)
    while True:
        try:
            jobs = await store.claim_due_jobs(WORKER_ID, 100)
            for job in jobs:
                job_id = int(job["id"])
                user_id = int(job["user_id"])
                job_type = str(job["job_type"])
                payload = job.get("payload") or {}
                try:
                    user = await store.get_user(user_id)
                    if not user or user.get("blocked") or user.get("automation_paused"):
                        await store.finish_job(job_id, "cancelled")
                        continue

                    # Targeted checkout/offer messages pause while a manual reply is pending.
                    # The broad cold reactivation campaign stays alive by design.
                    if job_type != "gate_6h" and not job_type.startswith("cold_") and await store.pending_reply(user_id):
                        await store.finish_job(job_id, "cancelled")
                        continue

                    lang = str(user.get("lang") or payload.get("lang") or "en")
                    origin_at = str(payload.get("origin_at") or job.get("scheduled_at"))
                    origin = _parse_time(origin_at)
                    last_admin = _parse_time(user.get("last_admin_reply_at"))

                    if job_type == "gate_6h":
                        member, can_verify = await _public_membership(bot, user_id, lang)
                        if member:
                            await store.set_public_membership(user_id, True, lang)
                            await store.track_event(user_id, "public_channel_verified", {"lang": lang, "source": "followup_check"})
                            await store.finish_job(job_id, "cancelled")
                            continue
                        if not can_verify:
                            await store.finish_job(job_id, "failed", "public channel cannot be resolved")
                            continue
                        await bot.send_message(
                            user_id,
                            followup_text(lang, job_type, user_id, str(user.get("first_name") or "")),
                            reply_markup=keyboards.public_gate_kb(lang),
                        )

                    elif job_type.startswith("cold_"):
                        # This branch intentionally reaches free users even when they
                        # have never opened the tariff/paywall screen.
                        if user.get("is_paid") or user.get("is_premium"):
                            await store.finish_job(job_id, "cancelled")
                            continue
                        stage = str(user.get("sales_stage") or "new")
                        if stage in {"offer_seen", "checkout_started", "checkout_abandoned", "paid"}:
                            await store.finish_job(job_id, "cancelled")
                            continue

                        day = int(payload.get("day") or 0)
                        market = str(user.get("market") or "global")
                        if not user.get("region_confirmed"):
                            markup = keyboards.region_confirm_kb(lang, market if market in {"ua", "cis", "eu", "us", "latam", "global"} else "global")
                        elif not user.get("public_channel_member"):
                            markup = keyboards.public_gate_kb(lang)
                        else:
                            markup = keyboards.followup_offer_kb(lang)

                        await bot.send_message(
                            user_id,
                            followup_text(
                                lang, job_type, user_id, str(user.get("first_name") or ""),
                                variant_seed=day or None,
                            ),
                            reply_markup=markup,
                        )
                        if job_type == "cold_daily":
                            next_when = datetime.now(timezone.utc) + timedelta(hours=24)
                            next_payload = dict(payload)
                            next_payload["day"] = max(day, 1) + 1
                            await store.schedule_job(
                                user_id,
                                "cold_daily",
                                next_when.isoformat(),
                                f"cold:{user_id}:{next_when.date().isoformat()}",
                                next_payload,
                            )

                    elif job_type.startswith("offer_"):
                        if await store.has_payment_since(user_id, origin_at):
                            await store.finish_job(job_id, "cancelled")
                            continue
                        checkout = await store.latest_event(user_id, "checkout_created", origin_at)
                        if checkout:
                            await store.finish_job(job_id, "cancelled")
                            continue
                        if origin and last_admin and last_admin > origin:
                            await store.finish_job(job_id, "cancelled")
                            continue
                        day = int(payload.get("day") or 0)
                        await bot.send_message(
                            user_id,
                            followup_text(
                                lang, job_type, user_id, str(user.get("first_name") or ""),
                                variant_seed=day or None,
                            ),
                            reply_markup=keyboards.followup_offer_kb(lang),
                        )
                        if job_type == "offer_daily":
                            next_day = max(day, 3) + 1
                            next_payload = dict(payload)
                            next_payload["day"] = next_day
                            offer_id = str(payload.get("offer_id") or f"u{user_id}")
                            await store.schedule_job(
                                user_id,
                                "offer_daily",
                                (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                                f"offer:{offer_id}:daily:{next_day}",
                                next_payload,
                            )

                    elif job_type.startswith("checkout_"):
                        if await store.has_payment_since(user_id, origin_at):
                            await store.finish_job(job_id, "cancelled")
                            continue
                        if origin and last_admin and last_admin > origin:
                            await store.finish_job(job_id, "cancelled")
                            continue
                        product = str(payload.get("product") or "plus")
                        market = str(payload.get("market") or user.get("market") or "global")
                        if product not in {"plus", "pro", "ultra", "black"}:
                            await store.finish_job(job_id, "failed", "unknown product")
                            continue

                        expires_at = _parse_time(payload.get("checkout_expires_at"))
                        if job_type in {"checkout_5m", "checkout_30m", "checkout_3h", "checkout_12h", "checkout_23h"} and expires_at and datetime.now(timezone.utc) >= expires_at:
                            await store.finish_job(job_id, "cancelled", "checkout link already expired")
                            continue

                        if job_type == "checkout_5m":
                            await store.update_user(user_id, sales_stage="checkout_abandoned")
                        day = int(payload.get("day") or 0)
                        invoice_url = str(payload.get("invoice_url") or "") if job_type != "checkout_daily" else None
                        await bot.send_message(
                            user_id,
                            followup_text(
                                lang, job_type, user_id, str(user.get("first_name") or ""),
                                variant_seed=day or None,
                            ),
                            reply_markup=keyboards.followup_checkout_kb(
                                lang, product, market, invoice_url=invoice_url or None
                            ),
                        )
                        if job_type == "checkout_daily":
                            next_day = max(day, 1) + 1
                            next_payload = dict(payload)
                            next_payload["day"] = next_day
                            checkout_id = str(payload.get("checkout_id") or f"u{user_id}")
                            await store.schedule_job(
                                user_id,
                                "checkout_daily",
                                (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                                f"checkout:{checkout_id}:daily:{next_day}",
                                next_payload,
                            )
                    else:
                        await store.finish_job(job_id, "failed", "unknown job type")
                        continue

                    await store.track_event(user_id, "sales_followup_sent", {
                        "job_type": job_type,
                        "job_id": job_id,
                        "checkout_id": payload.get("checkout_id"),
                        "product": payload.get("product"),
                        "day": payload.get("day"),
                    })
                    await store.finish_job(job_id, "sent")
                    await asyncio.sleep(0.08)

                except TelegramForbiddenError:
                    await store.mark_blocked(user_id)
                    await store.finish_job(job_id, "cancelled", "bot blocked")
                except Exception as exc:
                    logger.exception("Follow-up failed job=%s user=%s", job_id, user_id)
                    attempts = int(job.get("attempts") or 1)
                    retry_delay = 60 if attempts <= 1 else 300 if attempts == 2 else 900 if attempts == 3 else 3600
                    try:
                        await store.retry_job(job_id, str(exc), retry_delay)
                    except Exception:
                        logger.exception("Could not requeue failed follow-up job=%s", job_id)
                    await _system_alert(
                        bot,
                        "followup-job-error",
                        f"⚠️ <b>Follow-up error</b>\nJob: <code>{job_id}</code> · user <code>{user_id}</code>\n"
                        f"Попытка {attempts}; повтор примерно через {max(1, retry_delay // 60)} мин. "
                        f"Ошибка: <code>{str(exc)[:500]}</code>",
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Follow-up loop cycle failed")
            await _system_alert(
                bot,
                "followup-loop-error",
                f"🚨 <b>Воркер дожимов не может прочитать очередь</b>\n<code>{str(exc)[:700]}</code>\n\n"
                "Проверь SUPABASE_KEY: нужен service_role / sb_secret_, не anon/publishable.",
            )
        await asyncio.sleep(30)


async def delayed_reply_ai_loop(bot: Bot) -> None:
    """Optional fallback writer. No memory/XP/relationship logic; just recent chat -> one reply."""
    if not settings.auto_reply_ai:
        return
    while True:
        try:
            for row in await store.due_replies(settings.auto_reply_delay_minutes):
                user_id = int(row["user_id"])
                try:
                    user = await store.get_user(user_id)
                    if not user or user.get("blocked"):
                        await store.clear_pending_reply(user_id)
                        continue
                    history = await store.recent_messages(user_id, 12)
                    if not history or history[-1].get("role") != "user":
                        await store.clear_pending_reply(user_id)
                        continue
                    reply = await reply_ai.reply(
                        str(user.get("lang") or "en"),
                        history[:-1],
                        str(history[-1].get("content") or ""),
                    )
                    if not reply or not await store.pending_reply(user_id):
                        continue
                    await bot.send_message(user_id, reply, parse_mode=None)
                    await store.add_message(user_id, "assistant", reply)
                    await store.clear_pending_reply(user_id)
                    await store.update_user(user_id, last_admin_reply_at=datetime.now(timezone.utc).isoformat())
                    await store.track_event(user_id, "auto_reply_ai_sent")
                except TelegramForbiddenError:
                    await store.mark_blocked(user_id)
                except Exception:
                    logger.exception("Delayed reply AI failed for %s", user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Delayed reply AI loop failed")
        await asyncio.sleep(30)


async def run() -> None:
    settings.validate()
    await store.start()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Critical production check: direct messages may look healthy with an anon key,
    # while RLS silently breaks pending_replies and automation_jobs. Detect that
    # before accepting traffic.
    try:
        check = await store.operational_check()
    except Exception as exc:
        logger.exception("Supabase operational check failed")
        await _system_alert(
            bot,
            "startup-db-error",
            "🚨 <b>Victoria не запущена: база не даёт доступ к очереди.</b>\n\n"
            f"<code>{str(exc)[:900]}</code>\n\n"
            "На Render в SUPABASE_KEY должен быть server-side <b>service_role</b> / <b>sb_secret_</b> ключ, "
            "а не anon/publishable. После замены сделай redeploy.",
            cooldown_minutes=0,
        )
        await store.close()
        await bot.session.close()
        raise RuntimeError("Supabase operational check failed; follow-ups/admin inbox would be broken") from exc

    if settings.auto_reply_ai:
        await reply_ai.start()

    dispatcher = Dispatcher()
    limiter = SlidingWindowRateLimit()
    dispatcher.message.middleware(limiter)
    dispatcher.callback_query.middleware(limiter)
    dispatcher.include_router(router)

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.port)
    await site.start()

    tasks = [asyncio.create_task(channel_expiry_loop(bot), name="private-channel-expiry")]
    if settings.followups_enabled:
        tasks.append(asyncio.create_task(followup_loop(bot), name="sales-followups"))
        tasks.append(asyncio.create_task(global_reactivation_seed_loop(bot), name="global-reactivation-seeder"))
    if settings.auto_reply_ai:
        tasks.append(asyncio.create_task(delayed_reply_ai_loop(bot), name="reply-ai"))

    try:
        logger.info(
            "Victoria personal bot started · manual-first · AUTO_REPLY_AI=%s · FOLLOWUPS_ENABLED=%s · SUPABASE_KEY=%s",
            settings.auto_reply_ai,
            settings.followups_enabled,
            settings.supabase_key_kind,
        )
        await _system_alert(
            bot,
            "startup-ok",
            "🟢 <b>Victoria запущена</b>\n"
            f"Дожимы: <b>{'ON' if settings.followups_enabled else 'OFF'}</b>\n"
            f"AI auto-reply: <b>{'ON' if settings.auto_reply_ai else 'OFF'}</b>\n"
            f"Supabase: <b>OK</b> · key={settings.supabase_key_kind}\n"
            f"Pending jobs: <b>{int(check.get('pending_jobs', 0))}</b>",
            cooldown_minutes=0,
        )
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await runner.cleanup()
        if settings.auto_reply_ai:
            await reply_ai.close()
        await store.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass
