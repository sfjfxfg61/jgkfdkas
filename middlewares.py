from __future__ import annotations

import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class SlidingWindowRateLimit(BaseMiddleware):
    def __init__(self, max_events: int = 5, window_seconds: float = 4.0) -> None:
        super().__init__()
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(self, handler, event: TelegramObject, data: dict):
        actor = getattr(event, "from_user", None)
        if actor is None:
            return await handler(event, data)
        now = time.monotonic()
        bucket = self._events[actor.id]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_events:
            if isinstance(event, CallbackQuery):
                await event.answer("Too many actions. Try again in a few seconds.", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("Слишком быстро — подожди пару секунд.")
            return None
        bucket.append(now)
        return await handler(event, data)
