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
from database import store
from handlers import router
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


async def proactive_loop(bot: Bot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            now = datetime.now(timezone.utc)
            users = await store.eligible_for_proactive()
            for user in users:
                last_active = _parse_time(user.get("last_active_at"))
                last_sent = _parse_time(user.get("last_proactive_at"))
                if not last_active or now - last_active < timedelta(hours=20):
                    continue
                if last_sent and now - last_sent < timedelta(hours=settings.proactive_interval_hours):
                    continue
                try:
                    await bot.send_message(user["user_id"], t(user.get("lang", "en"), "proactive"))
                    await store.mark_proactive_sent(user["user_id"])
                    await asyncio.sleep(0.08)
                except TelegramForbiddenError:
                    await store.mark_blocked(user["user_id"])
                except Exception:
                    logger.exception("Proactive message failed for user %s", user["user_id"])
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Proactive loop cycle failed")
        await asyncio.sleep(3600)


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

    proactive_task = asyncio.create_task(proactive_loop(bot))
    try:
        logger.info("AI companion bot started")
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        proactive_task.cancel()
        await asyncio.gather(proactive_task, return_exceptions=True)
        await runner.cleanup()
        await companion_ai.close()
        await store.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass
