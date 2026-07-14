# middlewares.py

import time
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery, Message

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, limit: float = 1.0):
        self.limit = limit
        self.users = {}
        super().__init__()

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            now = time.time()
            last_time = self.users.get(user_id, 0)
            if now - last_time < self.limit:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⚠️ Пожалуйста, не нажимайте кнопки так быстро!", show_alert=True)
                    except Exception:
                        pass
                return
            self.users[user_id] = now
            
        return await handler(event, data)
