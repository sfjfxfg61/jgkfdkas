"""Relay incoming private messages; one registration RPC per Telegram message."""

from contextvars import ContextVar
import html
import logging
import re
from aiogram import BaseMiddleware
from aiogram.types import Message

current_user = ContextVar("victoria_user", default=None)
log = logging.getLogger(__name__)


class InboxMiddleware(BaseMiddleware):
    def __init__(self, store, cfg, lang_of=None):
        self.store, self.cfg = store, cfg

    async def __call__(self, handler, event: Message, data):
        tg = event.from_user
        if event.chat.type != "private":
            return
        if (
            not tg
            or tg.id == self.cfg.admin_id
            or event.successful_payment
            or event.refunded_payment
        ):
            return await handler(event, data)
        parts = (event.text or "").split(maxsplit=1)
        ref = "direct"
        if (
            parts
            and parts[0].split("@")[0] == "/start"
            and len(parts) == 2
            and re.fullmatch(r"[a-zA-Z0-9_]{1,48}", parts[1])
        ):
            ref = parts[1]
        u = await self.store.upsert_user(tg, ref=ref)
        kind = str(event.content_type)
        content = event.text or event.caption or f"[{kind}]"
        inserted = await self.store.message(tg.id, "user", content, event.message_id)
        if inserted:
            if not (event.text or "").startswith("/"):
                await self.store.ticket(tg.id)
                await self.store.event(
                    tg.id, "simple_support_message", content_type=kind
                )
            try:
                header = await data["bot"].send_message(
                    self.cfg.admin_id,
                    f"✉️ <b>{html.escape(tg.first_name or 'User')}</b> · 🌐 {html.escape(u.get('lang') or '?')}\n"
                    f"ID: <code>{tg.id}</code> · @{html.escape(tg.username or '—')}\n"
                    f"Тариф: {html.escape(u.get('subscription_tier') or 'free')}\n/user {tg.id}\n/send {tg.id} ответ",
                )
                await data["bot"].copy_message(
                    self.cfg.admin_id,
                    event.chat.id,
                    event.message_id,
                    reply_to_message_id=header.message_id,
                )
            except Exception:
                # Persistent inbox is authoritative even when Telegram forwarding is unavailable.
                log.warning(
                    "Admin relay unavailable user=%s; message retained in inbox", tg.id
                )
        token = current_user.set(u)
        try:
            return await handler(event, data)
        finally:
            current_user.reset(token)
