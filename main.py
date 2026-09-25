from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError

from ai_companion import companion_ai
from config import settings
from database import DatabaseError, store
from handlers import remove_channel_access, router
from monetization import entitlements
from domain import relationship_level
from middlewares import SlidingWindowRateLimit
from texts import t

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "ai-companion"})


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def reminder_stage_for_inactivity(inactive_for: timedelta) -> int:
    if inactive_for >= timedelta(days=7):
        return 3
    if inactive_for >= timedelta(days=3):
        return 2
    if inactive_for >= timedelta(days=1):
        return 1
    return 0


async def reminder_loop(bot: Bot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            now = datetime.now(timezone.utc)
            users = await store.eligible_for_reminders()
            for user in users:
                last_active = _parse_time(user.get("last_active_at"))
                if not last_active:
                    continue
                stage = reminder_stage_for_inactivity(now - last_active)
                if stage <= int(user.get("reminder_stage") or 0):
                    continue
                try:
                    stage_name = f"d{(1, 3, 7)[stage - 1]}"
                    await bot.send_message(user["user_id"], t(user.get("lang", "en"), f"reminder_{stage_name}"))
                    await store.mark_reminder_sent(user["user_id"], stage)
                    await store.track_event(user["user_id"], "reminder_sent", {"stage": stage_name})
                    await asyncio.sleep(0.08)
                except TelegramForbiddenError:
                    await store.mark_blocked(user["user_id"])
                except Exception:
                    logger.exception("Reminder failed for user %s", user["user_id"])
        except asyncio.CancelledError:
            raise
        except DatabaseError as exc:
            logger.error(
                "Reminders skipped because Supabase rejected the query. "
                "Run the complete schema.sql migration. Details: %s",
                exc,
            )
        except Exception:
            logger.exception("Reminder loop cycle failed")
        await asyncio.sleep(3600)


async def channel_expiry_loop(bot: Bot) -> None:
    if not settings.private_channel_ref:
        return
    while True:
        try:
            for user in await store.expired_members():
                try:
                    current = await store.get_user(user["user_id"])
                    if current and current.get("is_premium") and (
                        _parse_time(current.get("premium_until")) or datetime.min.replace(tzinfo=timezone.utc)
                    ) > datetime.now(timezone.utc):
                        continue
                    await remove_channel_access(bot, user["user_id"])
                except Exception:
                    logger.exception("Could not remove expired channel member %s", user["user_id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Channel expiry check failed")
        await asyncio.sleep(300)


async def delayed_reply_loop(bot: Bot) -> None:
    while True:
        try:
            for pending in await store.due_replies():
                user_id = pending["user_id"]
                if not await store.clear_pending_reply(user_id, pending["updated_at"]):
                    continue
                sent = False
                try:
                    user = await store.get_user(user_id)
                    if not user or user.get("human_takeover_until") and (
                        _parse_time(user["human_takeover_until"]) or datetime.min.replace(tzinfo=timezone.utc)
                    ) > datetime.now(timezone.utc):
                        continue
                    limits = entitlements(user.get("subscription_tier") or "free")
                    history = await store.recent_messages(user_id, limits.history_messages)
                    if not history or history[-1]["role"] != "user":
                        continue
                    reply = await companion_ai.reply(
                        lang=user["lang"], style=user.get("style", "warm"),
                        level=relationship_level(int(user.get("xp") or 0))[0],
                        memories=await store.memories(user_id, limits.memories),
                        history=history[:-1], user_text=history[-1]["content"], model=limits.model,
                    )
                    fresh = await store.get_user(user_id)
                    takeover = _parse_time((fresh or {}).get("human_takeover_until"))
                    if not reply:
                        await store.queue_reply(user_id)
                        continue
                    if not await store.pending_reply(user_id) and not (takeover and takeover > datetime.now(timezone.utc)):
                        await bot.send_message(user_id, reply)
                        sent = True
                        await store.add_message(user_id, "assistant", reply)
                        await store.track_event(user_id, "delayed_reply_sent")
                except Exception:
                    logger.exception("Delayed reply failed for %s", user_id)
                    if not sent:
                        await store.queue_reply(user_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Delayed reply loop failed")
        await asyncio.sleep(30)


async def run() -> None:
    settings.validate()
    await store.start()
    await companion_ai.start()

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

    reminder_task = asyncio.create_task(reminder_loop(bot))
    channel_task = asyncio.create_task(channel_expiry_loop(bot))
    delayed_task = asyncio.create_task(delayed_reply_loop(bot))
    try:
        logger.info("AI companion bot started")
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        reminder_task.cancel()
        channel_task.cancel()
        delayed_task.cancel()
        await asyncio.gather(reminder_task, channel_task, delayed_task, return_exceptions=True)
        await runner.cleanup()
        await companion_ai.close()
        await store.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass
