from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError

import keyboards
from config import settings
from database import store
from handlers import _public_membership, remove_channel_access, router
from middlewares import SlidingWindowRateLimit
from reply_ai import reply_ai
from sales_copy import followup_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


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


async def followup_loop(bot: Bot) -> None:
    if not settings.followups_enabled:
        return
    await asyncio.sleep(8)
    while True:
        try:
            jobs = await store.due_jobs(100)
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

                    # Never push a canned sales message while the person is waiting for a manual reply.
                    if job_type != "gate_6h" and await store.pending_reply(user_id):
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
                        if job_type in {"checkout_30m", "checkout_6h", "checkout_23h"} and expires_at and datetime.now(timezone.utc) >= expires_at:
                            await store.finish_job(job_id, "cancelled", "checkout link already expired")
                            continue

                        if job_type == "checkout_30m":
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
                            next_day = max(day, 2) + 1
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
                    await store.finish_job(job_id, "failed", str(exc))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Follow-up loop cycle failed")
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
    if settings.auto_reply_ai:
        await reply_ai.start()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
    if settings.auto_reply_ai:
        tasks.append(asyncio.create_task(delayed_reply_ai_loop(bot), name="reply-ai"))

    try:
        logger.info(
            "Victoria personal bot started · manual-first · AUTO_REPLY_AI=%s · FOLLOWUPS_ENABLED=%s",
            settings.auto_reply_ai,
            settings.followups_enabled,
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
