import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import database as db
import keyboards
from handlers import router
from texts import TEXTS

async def handle_ping(request):
    return web.Response(text="Bot is alive")

async def daily_retention_loop(bot: Bot):
    """
    Энергоэффективный воркер дожима. 
    Каждые 24 часа отправляет мягкий пуш-оффер с кнопкой оплаты тем, кто еще не купил.
    Занимает 0 Мб оперативной памяти, выполняется асинхронно.
    """
    await asyncio.sleep(10) # Старт после запуска ядра
    while True:
        try:
            logging.info("Running automated daily retention push...")
            unpaid = await db.db_get_unpaid_users()
            
            for user in unpaid:
                uid = user["user_id"]
                lang = user["lang"]
                try:
                    await bot.send_message(
                        chat_id=uid,
                        text=TEXTS[lang]["push"],
                        reply_markup=keyboards.trigger_kb(lang)
                    )
                    await asyncio.sleep(0.05) # Плавный лимитированный стриминг
                except Exception:
                    continue # Если заблокировал бота — идем дальше
            
            logging.info("Daily push routine finished cycle.")
        except Exception as e:
            logging.error(f"Error in daily retention loop: {e}")
        
        await asyncio.sleep(86400) # Засыпает ровно на 24 часа

async def main():
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    # Веб-сервер для поддержки Render веб-сервиса
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    
    logging.info(f"Keep-alive web server live on port {config.PORT}")

    # Запуск фонового демона триггер-рассылки (он привязан к таск-менеджеру ядра)
    asyncio.create_task(daily_retention_loop(bot))

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
