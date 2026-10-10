"""Local write-ahead journal. STATE_DIR must be on a persistent disk in production.
Telegram delivery is at-least-once: a crash between send and commit can duplicate a notice.
"""
from __future__ import annotations
import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from config import settings

logger = logging.getLogger(__name__)

class Journal:
    def __init__(self, directory=None):
        self.directory = Path(directory or settings.state_dir)
        self._connection = None

    @property
    def db(self):
        if self._connection is None:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._connection = sqlite3.connect(self.directory / 'recovery.sqlite3')
            self._connection.execute('PRAGMA journal_mode=WAL')
            self._connection.execute('PRAGMA synchronous=FULL')
            self._connection.executescript('''
            CREATE TABLE IF NOT EXISTS receipts(charge TEXT PRIMARY KEY, body TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS notices(key TEXT PRIMARY KEY, text TEXT NOT NULL, markup TEXT, done INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS cancellations(charge TEXT PRIMARY KEY, user_id INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0);
            ''')
        return self._connection

    def receipt(self, charge, body):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO receipts(charge,body) VALUES (?,?)', (charge, json.dumps(body)))

    def complete_receipt(self, charge):
        with self.db:
            self.db.execute('UPDATE receipts SET done=1 WHERE charge=?', (charge,))

    def notice(self, key, text, markup=None):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO notices(key,text,markup) VALUES (?,?,?)',
                            (key, text, markup.model_dump_json() if markup else None))

    def cancel_subscription(self, uid, charge):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO cancellations(charge,user_id) VALUES (?,?)', (charge,uid))

    def pending(self, table):
        if table not in {'receipts','notices','cancellations'}:
            raise ValueError('Invalid table')
        cur = self.db.execute(f'SELECT * FROM {table} WHERE done=0 LIMIT 50')
        keys = [d[0] for d in cur.description]
        return [dict(zip(keys,row)) for row in cur.fetchall()]

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None

journal = Journal()
_notice_lock = asyncio.Lock()

async def deliver_notices(bot):
    if not settings.admin_id:
        return
    async with _notice_lock:
        for row in journal.pending('notices'):
            try:
                markup = InlineKeyboardMarkup.model_validate_json(row['markup']) if row['markup'] else None
                await bot.send_message(settings.admin_id, row['text'], reply_markup=markup)
                with journal.db:
                    journal.db.execute('UPDATE notices SET done=1 WHERE key=?',(row['key'],))
            except Exception:
                logger.exception('Admin notification retained for retry')
                break

async def notify_admin(bot, key, text, reply_markup=None):
    journal.notice(key,text,reply_markup)
    await deliver_notices(bot)

async def recovery_loop(bot):
    from handlers import apply_paid_receipt, apply_refund_receipt, _lock
    from database import store
    while True:
        try:
            await deliver_notices(bot)
            for row in journal.pending('receipts'):
                try:
                    msg = Message.model_validate(json.loads(row['body']))
                    async with _lock(msg.from_user.id):
                        if msg.successful_payment:
                            await apply_paid_receipt(msg,bot)
                        else:
                            await apply_refund_receipt(msg,bot)
                        journal.complete_receipt(row['charge'])
                except Exception:
                    logger.exception('Financial receipt retained for recovery')
            # SQL cancellation outbox survives a crash immediately after activation.
            for row in await store.pending_subscription_cancellations():
                journal.cancel_subscription(int(row['user_id']),row['charge_id'])
            for row in journal.pending('cancellations'):
                try:
                    await bot.edit_user_star_subscription(row['user_id'],row['charge'],is_canceled=True)
                    await store.complete_subscription_cancellation(row['charge'])
                    with journal.db:
                        journal.db.execute('UPDATE cancellations SET done=1 WHERE charge=?',(row['charge'],))
                except Exception:
                    logger.exception('Previous subscription cancellation retained for retry')
                    await notify_admin(bot,f"cancel-warning:{row['charge']}",
                        f"⚠️ Не завершена отмена прежней подписки пользователя <code>{row['user_id']}</code>. Повторяем автоматически; проверь /user.")
            # Recover calls even if process died between request RPC and notification.
            for row in await store.pending_calls():
                await notify_admin(bot,f"call:{row['id']}",
                    f"📹 Заявка на видеозвонок · передай исполнителю\nЗаявка <code>{row['id']}</code> · user <code>{row['user_id']}</code>\nОтвет: <code>/send {row['user_id']} время</code>")
            await deliver_notices(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Recovery cycle failed; will retry')
        await asyncio.sleep(30)
