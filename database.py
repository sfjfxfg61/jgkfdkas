from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

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
                logger.error("Supabase %s %s failed: %s", method, path.split("?")[0], response.status)
                raise DatabaseError(f"Database request failed with status {response.status}")
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
            "lang": lang,
            "ref": (ref or "direct")[:80],
            "last_active_at": datetime.now(timezone.utc).isoformat(),
        }
        if not existing:
            payload["market"] = market
            payload["pricing_variant"] = "anchor" if user_id % 2 else "control"
        rows = await self._request(
            "POST", "users?on_conflict=user_id", json=payload,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

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

    async def eligible_for_proactive(self, limit: int = 100) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        return await self._request("GET", (
            "users?proactive_enabled=eq.true&onboarding_complete=eq.true&blocked=eq.false&is_premium=eq.true"
            f"&premium_until=gt.{now}"
            f"&select=user_id,lang,last_active_at,last_proactive_at&order=last_active_at.asc&limit={limit}"
        ))

    async def mark_proactive_sent(self, user_id: int) -> None:
        await self.update_user(user_id, last_proactive_at=datetime.now(timezone.utc).isoformat())

    async def mark_blocked(self, user_id: int) -> None:
        await self.update_user(user_id, blocked=True)

    async def stats(self) -> dict:
        result = await self._request("POST", "rpc/companion_admin_stats", json={})
        return result if isinstance(result, dict) else (result[0] if result else {})


store = SupabaseStore()
