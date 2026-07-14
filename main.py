# main.py

import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import database as db
import keyboards
from handlers import router as main_router
from middlewares import AntiFloodMiddleware
from texts import TEXTS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

async def handle_ping(request):
    """Эндпоинт для пинга от Uptime Robot / Render"""
    return web.Response(text="Bot is alive")

async def daily_retention_loop(bot: Bot):
    """
    Энергоэффективный воркер дожима. 
    Каждые 24 часа отправляет мягкий пуш-оффер с кнопкой оплаты тем, кто еще не купил.
    Безопасен к блокировкам — бот не упадет, если его заблокировали.
    """
    await asyncio.sleep(10)  # Старт после запуска ядра
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
                    await asyncio.sleep(0.05)  # Плавный лимитированный стриминг во избежание флуда
                except Exception:
                    # Если пользователь заблокировал бота — просто тихо идем дальше, бот не падает
                    continue
            
            logging.info("Daily push routine finished cycle.")
        except Exception as e:
            logging.error(f"Error in daily retention loop: {e}")
        
        await asyncio.sleep(86400)  # Засыпает ровно на 24 часа

async def main():
    bot = Bot(
        token=config.BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # 1. Регистрация Middleware для защиты от флуда и спама кнопками
    dp.message.middleware(AntiFloodMiddleware(limit=1.0))
    dp.callback_query.middleware(AntiFloodMiddleware(limit=1.0))
    
    # 2. Подключаем основной роутер
    dp.include_router(main_router)

    # 3. Веб-сервер для поддержки Render / Uptime Robot
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Порт берется из твоего config.py
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    
    logging.info(f"Keep-alive web server live on port {config.PORT}")

    # 4. Запуск фонового демона триггер-рассылки
    asyncio.create_task(daily_retention_loop(bot))

    # 5. Запуск получения обновлений (Polling)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped successfully!")
