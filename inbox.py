"""Private inbox relay independent of menu state; uses only existing tables."""
from __future__ import annotations
import html
import logging
import re
from aiogram import BaseMiddleware
from aiogram.types import Message

log = logging.getLogger(__name__)


class InboxMiddleware(BaseMiddleware):
    def __init__(self, store, cfg, lang_of):
        self.store, self.cfg, self.lang_of = store, cfg, lang_of

    async def __call__(self, handler, event: Message, data: dict):
        tg = event.from_user
        if event.chat.type != 'private':
            return None
        if not tg or tg.id == self.cfg.admin_id:
            return await handler(event, data)
        # Payment/service messages have their own handlers and are not user chat.
        if event.successful_payment or event.refunded_payment:
            return await handler(event, data)
        bot = data['bot']
        kind = str(event.content_type)
        content = event.text or event.caption or ''
        # Send identity first; copying media preserves photos, audio and documents.
        # No DB exception can silently prevent notification of the admin.
        try:
            header = await bot.send_message(self.cfg.admin_id,
                f'✉️ <b>Сообщение пользователя</b>\nID: <code>{tg.id}</code>\n'
                f'Имя: {html.escape(tg.first_name or "")}\n'
                f'Username: @{html.escape(tg.username or "—")}\n'
                f'Тип: {html.escape(kind)} · message_id: {event.message_id}\n'
                f'/send {tg.id} ответ')
            try:
                await bot.copy_message(self.cfg.admin_id, event.chat.id, event.message_id,
                                       reply_to_message_id=header.message_id)
            except Exception:
                log.exception('Message copy failed user=%s', tg.id)
                fallback = content or '[Telegram не разрешил копирование этого типа сообщения]'
                for offset in range(0, len(fallback), 3500):
                    await bot.send_message(self.cfg.admin_id, fallback[offset:offset + 3500],
                                           parse_mode=None, reply_to_message_id=header.message_id)
        except Exception:
            log.exception('Admin inbox delivery failed user=%s', tg.id)
        try:
            old = await self.store.get_user(tg.id)
            ref = 'direct'
            parts = (event.text or '').split(maxsplit=1)
            if parts and parts[0].split('@')[0] == '/start' and len(parts) == 2:
                if re.fullmatch(r'[a-zA-Z0-9_]{1,48}', parts[1].strip()):
                    ref = parts[1].strip()
            await self.store.upsert_user(tg, self.lang_of(old, tg.language_code), ref)
            recorded = content if event.text else f'[{kind}] {content}'
            await self.store.message(tg.id, 'user', recorded or f'[{kind}]')
            # Commands are archived/relayed, but do not create unanswered tickets.
            if not (event.text or '').startswith('/'):
                await self.store.ticket(tg.id)
                await self.store.event(tg.id, 'simple_support_message', content_type=kind)
        except Exception:
            log.exception('Inbox persistence failed user=%s', tg.id)
        return await handler(event, data)
