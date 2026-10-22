"""Async PostgREST backend. Atomic financial and queue operations live in SQL RPCs."""

from __future__ import annotations
import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
import time
from urllib.parse import urlencode
import aiohttp
from config import cfg
from words import telegram_language

log = logging.getLogger(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class StorageError(RuntimeError):
    pass


class Store:
    def __init__(self):
        self.session = None
        self.headers = {"apikey": cfg.db_key, "Content-Type": "application/json"}
        if cfg.db_key.count(".") == 2:
            self.headers["Authorization"] = "Bearer " + cfg.db_key
        self.root = cfg.db_url + "/rest/v1/"
        self.timings = deque(maxlen=1000)

    async def open(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            connector=aiohttp.TCPConnector(limit=20, limit_per_host=20),
        )

    async def close(self):
        if self.session:
            await self.session.close()

    async def req(self, method, table, *, params=None, body=None, prefer=None):
        if self.session is None:
            await self.open()
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        url = self.root + table + ("?" + urlencode(params) if params else "")
        # Only reads retry here. Mutations retry at their durable job boundary.
        for attempt in range(3 if method == "GET" else 1):
            started = time.monotonic()
            try:
                async with self.session.request(
                    method, url, json=body, headers=headers
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        # Do not log DB bodies, JWTs, message content or signed invoice payloads.
                        if resp.status >= 500 and method == "GET" and attempt < 2:
                            await asyncio.sleep(0.3 * 2**attempt)
                            continue
                        log.error("DB %s %s status=%s", method, table, resp.status)
                        raise StorageError(f"DB {resp.status}: {table}")
                    return await resp.json() if raw else []
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if method != "GET" or attempt == 2:
                    raise StorageError(f"DB unavailable: {table}") from exc
                await asyncio.sleep(0.3 * 2**attempt)
            finally:
                elapsed = time.monotonic() - started
                self.timings.append(elapsed)
                if elapsed > 2:
                    log.warning(
                        "Slow DB operation method=%s resource=%s ms=%d",
                        method,
                        table,
                        elapsed * 1000,
                    )

    async def rpc(self, name, **body):
        return await self.req("POST", "rpc/" + name, body=body)

    async def ping(self):
        info = await self.rpc("v4_metrics")
        if info.get("version") != 4:
            raise StorageError("Apply migrations/001_victoria_v4.sql before deployment")

    async def get_user(self, uid):
        rows = await self.req(
            "GET", "users", params={"user_id": f"eq.{uid}", "select": "*", "limit": "1"}
        )
        return rows[0] if rows else None

    async def upsert_user(self, tg, lang=None, ref="direct"):
        return await self.rpc(
            "v4_register",
            p_uid=int(tg.id),
            p_name=tg.first_name or "User",
            p_username=tg.username,
            p_lang=telegram_language(lang or getattr(tg, "language_code", None)),
            p_ref=ref,
            p_tz=cfg.reminder_timezone,
            p_clock=cfg.reminder_time,
        )

    async def patch(self, uid, *, current=None, **changes):
        changes["updated_at"] = now_iso()
        await self.req(
            "PATCH",
            "users",
            params={"user_id": f"eq.{uid}"},
            body=changes,
            prefer="return=minimal",
        )
        return {**(current or {"user_id": uid}), **changes}

    async def event(self, uid, event, **properties):
        # Funnel writes retry through durable updates. Worker bookkeeping may fail its job.
        await self.req(
            "POST",
            "events",
            body={"user_id": uid, "event": event, "properties": properties},
            prefer="return=minimal",
        )

    async def message(self, uid, role, content, telegram_message_id=None):
        body = {"user_id": uid, "role": role, "content": content[:8000]}
        if telegram_message_id is not None:
            body["telegram_message_id"] = telegram_message_id
            # PostgREST partial-index upsert is not supported; use unique insert and read on conflict.
            try:
                return await self.req(
                    "POST", "messages", body=body, prefer="return=representation"
                )
            except StorageError:
                old = await self.req(
                    "GET",
                    "messages",
                    params={
                        "user_id": f"eq.{uid}",
                        "telegram_message_id": f"eq.{telegram_message_id}",
                        "select": "id",
                        "limit": "1",
                    },
                )
                if old:
                    return []
                raise
        return await self.req("POST", "messages", body=body, prefer="return=minimal")

    async def ticket(self, uid):
        await self.req(
            "POST",
            "pending_replies",
            params={"on_conflict": "user_id"},
            body={"user_id": uid, "updated_at": now_iso()},
            prefer="resolution=merge-duplicates,return=minimal",
        )

    async def ticket_closed(self, uid, before_time=None):
        if before_time is None:
            return  # Do not erase an incoming ticket created after a reply began.
        await self.req(
            "DELETE",
            "pending_replies",
            params={"user_id": f"eq.{uid}", "updated_at": "lte." + before_time},
            prefer="return=minimal",
        )

    async def pending(self):
        return await self.req(
            "GET",
            "pending_replies",
            params={
                "select": "user_id,updated_at,users(first_name,lang,subscription_tier,premium_until)",
                "order": "updated_at.asc",
                "limit": "50",
            },
        )

    async def recent_messages(self, uid, limit=20, offset=0, archived=False):
        return await self.req(
            "GET",
            "messages_archive" if archived else "messages",
            params={
                "user_id": f"eq.{uid}",
                "select": "role,content,created_at",
                "order": "created_at.desc,id.desc",
                "limit": str(min(limit, 100)),
                "offset": str(max(0, offset)),
            },
        )

    async def payment_by_charge(self, charge):
        rows = await self.req(
            "GET",
            "payments",
            params={"telegram_charge_id": "eq." + charge, "select": "*", "limit": "1"},
        )
        return rows[0] if rows else None

    async def all_rows(self, table, select, params=None, limit=4000):
        result = []
        while limit is None or len(result) < limit:
            query = dict(params or {})
            query.update(
                select=select,
                limit=str(500 if limit is None else min(500, limit - len(result))),
                offset=str(len(result)),
            )
            rows = await self.req("GET", table, params=query)
            if not isinstance(rows, list):
                raise StorageError("Expected DB rows: " + table)
            result.extend(rows)
            if len(rows) < int(query["limit"]):
                break
        return result

    async def restore_receipts(self):
        # Grants are transactionally written with receipts; restore only the materialized user flags.
        users = await self.all_rows(
            "access_grants",
            "user_id",
            {
                "revoked_at": "is.null",
                "ends_at": "gt." + now_iso(),
                "order": "user_id.asc",
            },
            None,
        )
        ids = {int(u["user_id"]) for u in users}
        for uid in ids:
            await self.rpc("v4_sync_access", p_uid=uid)
        return len(ids)


store = Store()
