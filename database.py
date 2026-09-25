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
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))

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
                safe_body = body.replace(settings.supabase_key, "[redacted]")[:500]
                logger.error(
                    "Supabase %s %s failed: %s · %s",
                    method,
                    path.split("?")[0],
                    response.status,
                    safe_body,
                )
                raise DatabaseError(
                    f"Database request failed with status {response.status}: {safe_body}"
                )
            if not body:
                return None if allow_empty else []
            return await response.json()

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
        payload = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name[:100],
            "last_active_at": datetime.now(timezone.utc).isoformat(),
            "last_reminder_at": None,
            "reminder_stage": 0,
            "blocked": False,
        }
        if not existing:
            payload.update({
                "lang": lang,
                "ref": (ref or "direct")[:80],
                "market": market,
                "pricing_variant": "anchor" if user_id % 2 else "control",
            })
        rows = await self._request(
            "POST", "users?on_conflict=user_id", json=payload,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

    async def confirm_region(self, user_id: int, market: str) -> dict | None:
        # The condition also protects against a delayed/replayed onboarding button.
        rows = await self._request(
            "PATCH", f"users?user_id=eq.{user_id}&region_confirmed=eq.false",
            json={"market": market, "region_confirmed": True,
                  "onboarding_complete": True, "style": "playful"},
            prefer="return=representation",
        )
        return rows[0] if rows else None

    async def get_user(self, user_id: int) -> dict | None:
        rows = await self._request("GET", f"users?user_id=eq.{user_id}&select=*")
        return rows[0] if rows else None

    async def update_user(self, user_id: int, **values: Any) -> dict:
        rows = await self._request(
            "PATCH", f"users?user_id=eq.{user_id}", json=values, prefer="return=representation"
        )
        if not rows:
            raise DatabaseError("User not found")
        return rows[0]

    async def consume_quota(self, user_id: int, daily_limit: int) -> dict:
        result = await self._request("POST", "rpc/consume_message_quota", json={
            "p_user_id": user_id,
            "p_daily_limit": daily_limit,
        })
        return result if isinstance(result, dict) else (result[0] if result else {"allowed": False, "remaining": 0})

    async def add_message(self, user_id: int, role: str, content: str) -> None:
        await self._request(
            "POST", "messages", json={"user_id": user_id, "role": role, "content": content[:8000]},
            prefer="return=minimal", allow_empty=True,
        )

    async def recent_messages(self, user_id: int, limit: int) -> list[dict]:
        rows = await self._request(
            "GET", f"messages?user_id=eq.{user_id}&select=role,content,created_at&order=created_at.desc&limit={limit}"
        )
        return list(reversed(rows))

    async def memories(self, user_id: int, limit: int = 24) -> list[dict]:
        return await self._request(
            "GET", f"memories?user_id=eq.{user_id}&select=memory_key,memory_value,confidence&order=updated_at.desc&limit={limit}"
        )

    async def upsert_memories(self, user_id: int, items: list[dict]) -> None:
        rows = []
        for item in items[:8]:
            key = str(item.get("key", "")).strip()[:80]
            value = str(item.get("value", "")).strip()[:500]
            try:
                confidence = float(item.get("confidence", 0.8))
            except (TypeError, ValueError):
                confidence = 0.8
            if key and value:
                rows.append({
                    "user_id": user_id,
                    "memory_key": key,
                    "memory_value": value,
                    "confidence": max(0.0, min(confidence, 1.0)),
                })
        if rows:
            await self._request(
                "POST", "memories?on_conflict=user_id,memory_key", json=rows,
                prefer="resolution=merge-duplicates,return=minimal", allow_empty=True,
            )

    async def clear_user_memory(self, user_id: int) -> None:
        await self._request("DELETE", f"messages?user_id=eq.{user_id}", prefer="return=minimal", allow_empty=True)
        await self._request("DELETE", f"memories?user_id=eq.{user_id}", prefer="return=minimal", allow_empty=True)
        await self.update_user(user_id, xp=0, total_messages=0)

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
        return result if isinstance(result, dict) else (result[0] if result else {})

    async def track_event(self, user_id: int, event: str, properties: dict | None = None) -> None:
        try:
            await self._request(
                "POST",
                "events",
                json={"user_id": user_id, "event": event[:80], "properties": properties or {}},
                prefer="return=minimal",
                allow_empty=True,
            )
        except DatabaseError:
            logger.warning("Unable to track event %s for user %s", event, user_id)

    async def mark_payment_refunded(self, charge_id: str) -> dict:
        result = await self._request(
            "POST", "rpc/mark_payment_refunded", json={"p_charge_id": charge_id}
        )
        return result if isinstance(result, dict) else (result[0] if result else {})

    async def eligible_for_reminders(self, limit: int = 500) -> list[dict]:
        # PostgREST query strings treat an unescaped '+' as a space. Use UTC Z form.
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
        return await self._request("GET", (
            "users?onboarding_complete=eq.true&blocked=eq.false&reminder_stage=lt.3"
            f"&last_active_at=lt.{cutoff}"
            "&select=user_id,lang,total_messages,last_active_at,last_reminder_at,reminder_stage"
            f"&order=last_active_at.asc&limit={limit}"
        ))

    async def mark_reminder_sent(self, user_id: int, stage: int) -> None:
        await self.update_user(
            user_id,
            reminder_stage=stage,
            last_reminder_at=datetime.now(timezone.utc).isoformat(),
        )

    async def mark_blocked(self, user_id: int) -> None:
        await self.update_user(user_id, blocked=True)
        await self.track_event(user_id, "bot_blocked")

    async def reminder_was_engaged(self, user_id: int, since: str) -> bool:
        rows = await self._request(
            "GET", f"events?user_id=eq.{user_id}&event=in.(reminder_clicked,reminder_returned)"
            f"&created_at=gte.{quote(since.replace('+00:00', 'Z'), safe=':-TZ.')}&select=id&limit=1",
        )
        return bool(rows)

    async def last_reminder_properties(self, user_id: int) -> dict:
        rows = await self._request(
            "GET", f"events?user_id=eq.{user_id}&event=eq.reminder_sent"
            "&select=properties&order=created_at.desc,id.desc&limit=1",
        )
        return rows[0].get("properties") or {} if rows else {}

    async def expired_members(self, limit: int = 100) -> list[dict]:
        cutoff = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return await self._request(
            "GET", "users?channel_member=eq.true"
            f"&or=(premium_until.is.null,premium_until.lt.{cutoff})&select=user_id&limit={limit}"
        )

    async def queue_reply(self, user_id: int) -> None:
        await self._request(
            "POST", "pending_replies?on_conflict=user_id",
            json={"user_id": user_id, "updated_at": datetime.now(timezone.utc).isoformat()},
            prefer="resolution=merge-duplicates,return=minimal", allow_empty=True,
        )

    async def record_chat_activity(self, user_id: int) -> None:
        await self._request("POST", "rpc/record_chat_activity", json={"p_user_id": user_id})

    async def request_call(self, user_id: int) -> dict:
        result = await self._request("POST", "rpc/request_paid_call", json={"p_user_id": user_id})
        return result if isinstance(result, dict) else result[0]

    async def pending_calls(self) -> list[dict]:
        return await self._request("GET", "call_requests?status=eq.pending&select=id,user_id,created_at&order=created_at.asc&limit=50")

    async def complete_call(self, request_id: int) -> bool:
        rows = await self._request("PATCH", f"call_requests?id=eq.{request_id}&status=eq.pending",
                                   json={"status": "completed"}, prefer="return=representation")
        return bool(rows)

    async def cancel_call(self, request_id: int) -> bool:
        rows = await self._request("PATCH", f"call_requests?id=eq.{request_id}&status=eq.pending",
                                   json={"status": "canceled"}, prefer="return=representation")
        return bool(rows)

    async def due_replies(self, limit: int = 50) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        return await self._request("GET", f"pending_replies?updated_at=lte.{cutoff}&select=user_id,updated_at&order=updated_at.asc&limit={limit}")

    async def reply_queue(self) -> list[dict]:
        return await self._request("GET", "pending_replies?select=user_id,updated_at&order=updated_at.asc&limit=50")

    async def pending_reply(self, user_id: int) -> bool:
        rows = await self._request("GET", f"pending_replies?user_id=eq.{user_id}&select=user_id&limit=1")
        return bool(rows)

    async def clear_pending_reply(self, user_id: int, updated_at: str | None = None) -> bool:
        path = f"pending_replies?user_id=eq.{user_id}"
        if updated_at:
            path += f"&updated_at=eq.{quote(updated_at, safe='')}"
        rows = await self._request("DELETE", path, prefer="return=representation")
        return bool(rows)

    async def stats(self) -> dict:
        result = await self._request("POST", "rpc/companion_admin_stats", json={})
        stats = result if isinstance(result, dict) else (result[0] if result else {})
        retention = await self._request("POST", "rpc/companion_retention_days", json={})
        stats["retention"] = retention if isinstance(retention, dict) else (retention[0] if retention else {})
        membership = await self._request("POST", "rpc/companion_membership_stats", json={})
        stats["membership"] = membership if isinstance(membership, dict) else (membership[0] if membership else {})
        health = await self._request("POST", "rpc/companion_health_stats", json={})
        stats["health"] = health if isinstance(health, dict) else (health[0] if health else {})
        return stats


store = SupabaseStore()
