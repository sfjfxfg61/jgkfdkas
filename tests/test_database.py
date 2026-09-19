import pytest

from database import SupabaseStore


@pytest.mark.asyncio
async def test_reminder_query_uses_postgrest_safe_utc_timestamp(monkeypatch) -> None:
    captured: dict[str, str] = {}
    store = SupabaseStore()

    async def fake_request(method: str, path: str, **_: object) -> list[dict]:
        captured["method"] = method
        captured["path"] = path
        return []

    monkeypatch.setattr(store, "_request", fake_request)
    assert await store.eligible_for_reminders() == []
    assert captured["method"] == "GET"
    assert "+00:00" not in captured["path"]
    assert "last_active_at=lt." in captured["path"]
    assert "total_messages=gt.0" in captured["path"]
    assert "reminder_stage=lt.3" in captured["path"]
    assert "is_premium" not in captured["path"]
    assert "Z" in captured["path"]
