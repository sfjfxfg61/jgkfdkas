"""Only existing Supabase tables. No destructive schema migration.

The old users / historical premium flags are never reset during onboarding.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import logging
from urllib.parse import urlencode
import aiohttp
from config import cfg
from catalog import default_market

log = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StorageError(RuntimeError):
    pass


class Store:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
        self.headers = {'apikey': cfg.db_key, 'Content-Type': 'application/json'}
        # New sb_secret_ keys are not JWTs. Legacy service_role JWTs are.
        if cfg.db_key.count('.') == 2:
            self.headers['Authorization'] = 'Bearer ' + cfg.db_key
        self.root = cfg.db_url + '/rest/v1/'

    async def open(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))

    async def close(self):
        if self.session:
            await self.session.close()

    async def req(self, method: str, table: str, *, params: dict | None = None,
                  body=None, prefer: str | None = None):
        if self.session is None:
            await self.open()
        headers = dict(self.headers)
        if prefer:
            headers['Prefer'] = prefer
        query = ('?' + urlencode(params)) if params else ''
        url = self.root + table + query
        assert self.session
        async with self.session.request(method, url, json=body, headers=headers) as resp:
            raw = await resp.text()
            if resp.status >= 400:
                safe = raw.replace(cfg.db_key, '[redacted]')[:500]
                log.error('DB %s %s: %s %s', method, table, resp.status, safe)
                raise StorageError(f'DB error {resp.status} in {table}: {safe}')
            if not raw:
                return []
            try:
                return await resp.json()
            except aiohttp.ContentTypeError as exc:
                raise StorageError('Non-JSON DB result') from exc

    async def ping(self):
        await self.req('GET', 'users', params={'select': 'user_id', 'limit': '1'})
        await self.req('GET', 'payments', params={'select': 'id', 'limit': '1'})
        await self.req('GET', 'pending_replies', params={'select': 'user_id', 'limit': '1'})

    async def get_user(self, uid: int):
        rows = await self.req('GET', 'users', params={'user_id': f'eq.{uid}', 'select': '*', 'limit': '1'})
        return rows[0] if rows else None

    async def upsert_user(self, tg, lang: str, ref: str = 'direct'):
        uid = int(tg.id)
        existing = await self.get_user(uid)
        base = {
            'user_id': uid,
            'first_name': (tg.first_name or 'User')[:100],
            'username': tg.username,
            'last_active_at': now_iso(), 'updated_at': now_iso(), 'blocked': False,
        }
        if not existing:
            base.update({'lang': lang, 'ref': ref[:80], 'market': default_market(lang),
                         'sales_stage': 'new'})
        rows = await self.req('POST', 'users', params={'on_conflict': 'user_id'}, body=base,
                              prefer='resolution=merge-duplicates,return=representation')
        return rows[0]

    async def patch(self, uid: int, **changes):
        changes['updated_at'] = now_iso()
        rows = await self.req('PATCH', 'users', params={'user_id': f'eq.{uid}'},
                              body=changes, prefer='return=representation')
        if not rows:
            raise StorageError(f'User {uid} not found')
        return rows[0]

    async def event(self, uid: int, event: str, **properties):
        try:
            await self.req('POST', 'events', body={
                'user_id': uid, 'event': event, 'properties': properties,
            }, prefer='return=minimal')
        except Exception:
            log.exception('Optional event %s could not be stored', event)

    async def message(self, uid: int, role: str, content: str):
        await self.req('POST', 'messages', body={'user_id': uid, 'role': role,
                                                'content': content[:8000]}, prefer='return=minimal')

    async def ticket(self, uid: int):
        await self.req('POST', 'pending_replies', params={'on_conflict': 'user_id'},
                       body={'user_id': uid, 'updated_at': now_iso()},
                       prefer='resolution=merge-duplicates,return=minimal')

    async def ticket_closed(self, uid: int, before_time: str | None = None):
        params = {'user_id': f'eq.{uid}'}
        if before_time:
            params['updated_at'] = 'lte.' + before_time
        await self.req('DELETE', 'pending_replies', params=params, prefer='return=minimal')

    async def pending(self):
        return await self.all_rows('pending_replies', 'user_id,updated_at',
                                   {'order': 'updated_at.desc'}, 500)

    async def recent_messages(self, uid: int, limit: int = 10):
        return await self.req('GET', 'messages', params={'user_id': f'eq.{uid}',
                  'select': 'role,content,created_at', 'order': 'created_at.desc', 'limit': str(limit)})

    async def payment_by_charge(self, charge: str):
        rows = await self.req('GET', 'payments', params={'telegram_charge_id': f'eq.{charge}',
             'select': '*', 'limit': '1'})
        return rows[0] if rows else None

    async def save_receipt(self, uid: int, charge: str, payload: str, amount: int,
                           plan: str, duration: int, until: datetime, market: str = 'global'):
        exists = await self.payment_by_charge(charge)
        if exists:
            return exists, True
        receipt = {
            'user_id': uid, 'telegram_charge_id': charge, 'payload': payload,
            'amount': amount, 'currency': 'XTR', 'plan': plan, 'market': market,
            'pricing_variant': 'simple', 'duration_days': duration,
            'recurring': False, 'entitlement_until': until.isoformat(),
        }
        try:
            res = await self.req('POST', 'payments', body=receipt, prefer='return=representation')
            return res[0], False
        except StorageError:
            # Potential simultaneous Telegram delivery; check UNIQUE charge again.
            exists = await self.payment_by_charge(charge)
            if exists:
                return exists, True
            raise

    async def grant_from_receipt(self, receipt: dict):
        uid = int(receipt['user_id'])
        u = await self.get_user(uid)
        if not u:
            raise StorageError('Cannot activate payment without user row')
        desired = str(receipt.get('entitlement_until') or '')
        if not desired or receipt.get('refunded_at'):
            return u
        existing = str(u.get('premium_until') or '')
        # Both are ISO 8601 UTC; parse to avoid textual timezone mistakes.
        def parse(value):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return datetime.min.replace(tzinfo=timezone.utc)
        if parse(existing) >= parse(desired) and u.get('is_premium') and u.get('is_paid'):
            return u
        return await self.patch(uid, is_paid=True, is_premium=True, blocked=False,
                                premium_until=max(parse(existing), parse(desired)).isoformat(),
                                subscription_tier=str(receipt.get('plan') or 'trial'),
                                subscription_recurring=False,
                                subscription_charge_id=str(receipt.get('telegram_charge_id')),
                                last_payment_at=now_iso(), sales_stage='paid',
                                subscription_payload=receipt.get('payload'))


    async def refund_receipt(self, charge: str) -> dict | None:
        receipt = await self.payment_by_charge(charge)
        if not receipt:
            return None
        if not receipt.get('refunded_at'):
            await self.req('PATCH', 'payments',
                           params={'telegram_charge_id': f'eq.{charge}'},
                           body={'refunded_at': now_iso()}, prefer='return=minimal')
        return receipt

    async def all_rows(self, table: str, select: str, params: dict | None = None,
                       limit: int | None = 4000):
        # Explicit pagination, not Supabase default first 1000 rows.
        result = []
        while limit is None or len(result) < limit:
            query = dict(params or {})
            query['select'] = select
            query['limit'] = str(500 if limit is None else min(500, limit - len(result)))
            query['offset'] = str(len(result))
            rows = await self.req('GET', table, params=query)
            if not isinstance(rows, list):
                raise StorageError(f'Expected list for {table}')
            result.extend(rows)
            if len(rows) < int(query['limit']):
                break
        return result

    async def restore_receipts(self):
        # Safe, idempotent and no old paid users are ever downgraded.
        rows = await self.all_rows('payments', '*', {'refunded_at': 'is.null', 'order': 'created_at.asc'}, 5000)
        repaired = 0
        for receipt in rows:
            u = await self.get_user(int(receipt['user_id']))
            if not u:
                continue
            from catalog import active
            existing = str(u.get('premium_until') or '')
            goal = str(receipt.get('entitlement_until') or '')
            if goal and (not active(u) or existing < goal) and u.get('subscription_tier') != 'black':
                await self.grant_from_receipt(receipt)
                repaired += 1
        return repaired

store = Store()
