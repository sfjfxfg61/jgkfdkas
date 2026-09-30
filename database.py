from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import aiohttp

from config import settings

logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    pass


class SupabaseStore:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._base = f"{settings.supabase_url}/rest/v1"
        self._headers = {
            "apikey": settings.supabase_key,
            "Authorization": f"Bearer {settings.supabase_key}",
            "Content-Type": "application/json",
        }

    async def start(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        prefer: str | None = None,
        allow_empty: bool = False,
    ) -> Any:
        if not self._session or self._session.closed:
            await self.start()
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        assert self._session is not None
        async with self._session.request(method, f"{self._base}/{path}", json=json, headers=headers) as response:
            body = await response.text()
            if response.status >= 400:
                safe = body.replace(settings.supabase_key, "[redacted]")[:1000]
                logger.error("Supabase %s %s failed: %s · %s", method, path.split("?")[0], response.status, safe)
                raise DatabaseError(f"Database request failed with status {response.status}: {safe}")
            if not body:
                return None if allow_empty else []
            return await response.json()

    # Users --------------------------------------------------------------
    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
        lang: str,
        ref: str,
        market: str,
    ) -> dict:
        existing = await self.get_user(user_id)
        now = datetime.now(timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "user_id": user_id,
            "username": username,
            "first_name": (first_name or "User")[:100],
            "last_active_at": now,
            "blocked": False,
            "updated_at": now,
        }
        if not existing:
            payload.update({
                "lang": lang,
                "ref": (ref or "direct")[:80],
                "market": market,
                "pricing_variant": "control",
                "sales_stage": "new",
            })
        rows = await self._request(
            "POST",
            "users?on_conflict=user_id",
            json=payload,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

    async def get_user(self, user_id: int) -> dict | None:
        rows = await self._request("GET", f"users?user_id=eq.{user_id}&select=*")
        return rows[0] if rows else None

    async def update_user(self, user_id: int, **values: Any) -> dict:
        values["updated_at"] = datetime.now(timezone.utc).isoformat()
        rows = await self._request(
            "PATCH",
            f"users?user_id=eq.{user_id}",
            json=values,
            prefer="return=representation",
        )
        if not rows:
            raise DatabaseError("User not found")
        return rows[0]

    async def set_region(self, user_id: int, market: str) -> dict:
        return await self.update_user(user_id, market=market, region_confirmed=True, onboarding_complete=True)

    async def set_language(self, user_id: int, lang: str) -> dict:
        return await self.update_user(
            user_id,
            lang=lang,
            public_channel_member=False,
            public_channel_lang=None,
            public_channel_checked_at=None,
        )

    async def set_public_membership(self, user_id: int, member: bool, lang: str) -> dict:
        values: dict[str, Any] = {
            "public_channel_member": member,
            "public_channel_checked_at": datetime.now(timezone.utc).isoformat(),
        }
        if member:
            values["public_channel_lang"] = lang
            user = await self.get_user(user_id)
            if user and user.get("sales_stage") in {None, "new", "channel_required"}:
                values["sales_stage"] = "channel_joined"
        return await self.update_user(user_id, **values)

    async def mark_blocked(self, user_id: int) -> None:
        try:
            await self.update_user(user_id, blocked=True, sales_stage="blocked")
        finally:
            await self.cancel_jobs(user_id)
            await self.clear_pending_reply(user_id)
            await self.track_event(user_id, "bot_blocked")

    # Conversation log / manual inbox ----------------------------------
    async def add_message(self, user_id: int, role: str, content: str) -> None:
        await self._request(
            "POST",
            "messages",
            json={"user_id": user_id, "role": role, "content": content[:8000]},
            prefer="return=minimal",
            allow_empty=True,
        )

    async def recent_messages(self, user_id: int, limit: int = 20) -> list[dict]:
        rows = await self._request(
            "GET",
            f"messages?user_id=eq.{user_id}&select=role,content,created_at&order=created_at.desc&limit={max(1, min(limit, 100))}",
        )
        return list(reversed(rows))

    async def last_message(self, user_id: int, role: str | None = None) -> dict | None:
        path = f"messages?user_id=eq.{user_id}"
        if role:
            path += f"&role=eq.{quote(role, safe='')}"
        path += "&select=role,content,created_at&order=created_at.desc,id.desc&limit=1"
        rows = await self._request("GET", path)
        return rows[0] if rows else None

    async def record_chat_activity(self, user_id: int) -> None:
        await self._request("POST", "rpc/record_chat_activity", json={"p_user_id": user_id})
        user = await self.get_user(user_id)
        if user and user.get("sales_stage") in {None, "new", "channel_joined", "channel_required"}:
            await self.update_user(user_id, sales_stage="engaged")

    async def queue_reply(self, user_id: int) -> None:
        await self._request(
            "POST",
            "pending_replies?on_conflict=user_id",
            json={"user_id": user_id, "updated_at": datetime.now(timezone.utc).isoformat()},
            prefer="resolution=merge-duplicates,return=minimal",
            allow_empty=True,
        )

    async def reply_queue(self) -> list[dict]:
        return await self._request("GET", "pending_replies?select=user_id,updated_at&order=updated_at.asc&limit=100")

    async def pending_reply(self, user_id: int) -> bool:
        rows = await self._request("GET", f"pending_replies?user_id=eq.{user_id}&select=user_id&limit=1")
        return bool(rows)

    async def clear_pending_reply(self, user_id: int) -> bool:
        rows = await self._request(
            "DELETE",
            f"pending_replies?user_id=eq.{user_id}",
            prefer="return=representation",
        )
        return bool(rows)

    async def due_replies(self, minutes: int, limit: int = 50) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")
        safe = quote(cutoff, safe=":-TZ.")
        return await self._request(
            "GET",
            f"pending_replies?updated_at=lte.{safe}&select=user_id,updated_at&order=updated_at.asc&limit={limit}",
        )

    # Events / analytics ------------------------------------------------
    async def track_event(self, user_id: int, event: str, properties: dict | None = None) -> dict | None:
        try:
            rows = await self._request(
                "POST",
                "events",
                json={"user_id": user_id, "event": event[:80], "properties": properties or {}},
                prefer="return=representation",
            )
            return rows[0] if rows else None
        except DatabaseError:
            logger.warning("Unable to track event %s for user %s", event, user_id, exc_info=True)
            return None

    async def latest_event(self, user_id: int, event: str, since: str | None = None) -> dict | None:
        path = f"events?user_id=eq.{user_id}&event=eq.{quote(event, safe='')}&select=id,event,properties,created_at"
        if since:
            path += f"&created_at=gte.{quote(since.replace('+00:00', 'Z'), safe=':-TZ.')}"
        path += "&order=created_at.desc,id.desc&limit=1"
        rows = await self._request("GET", path)
        return rows[0] if rows else None

    async def stats(self) -> dict:
        result = await self._request("POST", "rpc/victoria_sales_stats", json={})
        return result if isinstance(result, dict) else (result[0] if result else {})

    # Payments ----------------------------------------------------------
    async def record_payment(
        self,
        user_id: int,
        charge_id: str,
        payload: str,
        amount: int,
        plan: str,
        market: str,
        duration_days: int,
        recurring: bool,
        expires_at: str | None = None,
    ) -> dict:
        result = await self._request("POST", "rpc/record_payment_and_activate", json={
            "p_user_id": user_id,
            "p_charge_id": charge_id,
            "p_payload": payload,
            "p_amount": amount,
            "p_plan": plan,
            "p_market": market,
            "p_days": duration_days,
            "p_recurring": recurring,
            "p_expires_at": expires_at,
        })
        await self.update_user(user_id, sales_stage="paid", last_payment_at=datetime.now(timezone.utc).isoformat())
        return result if isinstance(result, dict) else (result[0] if result else {})

    async def has_payment_since(self, user_id: int, since: str) -> bool:
        safe_since = quote(since.replace("+00:00", "Z"), safe=":-TZ.")
        rows = await self._request(
            "GET",
            f"payments?user_id=eq.{user_id}&refunded_at=is.null&created_at=gte.{safe_since}&select=id&limit=1",
        )
        return bool(rows)

    async def mark_payment_refunded(self, charge_id: str) -> dict:
        result = await self._request("POST", "rpc/mark_payment_refunded", json={"p_charge_id": charge_id})
        return result if isinstance(result, dict) else (result[0] if result else {})

    async def expired_members(self, limit: int = 100) -> list[dict]:
        cutoff = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return await self._request(
            "GET",
            "users?channel_member=eq.true"
            f"&or=(premium_until.is.null,premium_until.lt.{cutoff})&select=user_id&limit={limit}",
        )

    # Sales follow-up jobs ---------------------------------------------
    async def schedule_job(
        self,
        user_id: int,
        job_type: str,
        scheduled_at: str,
        dedupe_key: str,
        payload: dict | None = None,
    ) -> None:
        if not settings.followups_enabled:
            return
        await self._request(
            "POST",
            "automation_jobs?on_conflict=dedupe_key",
            json={
                "user_id": user_id,
                "job_type": job_type,
                "status": "pending",
                "scheduled_at": scheduled_at,
                "dedupe_key": dedupe_key[:180],
                "payload": payload or {},
            },
            prefer="resolution=ignore-duplicates,return=minimal",
            allow_empty=True,
        )

    async def due_jobs(self, limit: int = 100) -> list[dict]:
        now = quote(datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), safe=":-TZ.")
        return await self._request(
            "GET",
            f"automation_jobs?status=eq.pending&scheduled_at=lte.{now}"
            "&select=id,user_id,job_type,scheduled_at,payload,dedupe_key"
            f"&order=scheduled_at.asc&limit={limit}",
        )

    async def finish_job(self, job_id: int, status: str, error: str | None = None) -> None:
        values: dict[str, Any] = {"status": status}
        if status == "sent":
            values["sent_at"] = datetime.now(timezone.utc).isoformat()
        if error:
            values["last_error"] = error[:500]
        await self._request(
            "PATCH",
            f"automation_jobs?id=eq.{job_id}&status=eq.pending",
            json=values,
            prefer="return=minimal",
            allow_empty=True,
        )

    async def cancel_jobs(self, user_id: int, job_types: list[str] | None = None) -> None:
        path = f"automation_jobs?user_id=eq.{user_id}&status=eq.pending"
        if job_types:
            safe = ",".join(quote(x, safe="_") for x in job_types)
            path += f"&job_type=in.({safe})"
        await self._request("PATCH", path, json={"status": "cancelled"}, prefer="return=minimal", allow_empty=True)

    # Paid calls --------------------------------------------------------
    async def request_call(self, user_id: int) -> dict:
        result = await self._request("POST", "rpc/request_paid_call", json={"p_user_id": user_id})
        return result if isinstance(result, dict) else (result[0] if result else {})

    async def pending_calls(self) -> list[dict]:
        return await self._request(
            "GET",
            "call_requests?status=eq.pending&select=id,user_id,created_at&period_end&order=created_at.asc&limit=50",
        )

    async def complete_call(self, request_id: int) -> bool:
        rows = await self._request(
            "PATCH",
            f"call_requests?id=eq.{request_id}&status=eq.pending",
            json={"status": "completed"},
            prefer="return=representation",
        )
        return bool(rows)

    async def cancel_call(self, request_id: int) -> bool:
        rows = await self._request(
            "PATCH",
            f"call_requests?id=eq.{request_id}&status=eq.pending",
            json={"status": "canceled"},
            prefer="return=representation",
        )
        return bool(rows)


store = SupabaseStore()
