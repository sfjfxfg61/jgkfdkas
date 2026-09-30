import pytest

from database import SupabaseStore


@pytest.mark.asyncio
async def test_existing_user_market_is_not_overwritten_on_start(monkeypatch) -> None:
    store = SupabaseStore()
    captured: dict = {}

    async def get_user(_: int) -> dict:
        return {"user_id": 42, "market": "eu", "lang": "en", "ref": "threads"}

    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict]:
        captured.update(kwargs.get("json", {}))
        return [{"market": "eu", "lang": "en"}]

    monkeypatch.setattr(store, "get_user", get_user)
    monkeypatch.setattr(store, "_request", fake_request)
    await store.upsert_user(42, "name", "Name", "uk", "new_ref", "ua")
    assert "market" not in captured
    assert "lang" not in captured
    assert "ref" not in captured


@pytest.mark.asyncio
async def test_region_confirmation_is_conditional(monkeypatch) -> None:
    store = SupabaseStore()
    captured: dict = {}

    async def fake_request(method: str, path: str, **kwargs: object) -> list[dict]:
        captured.update({"method": method, "path": path, "payload": kwargs.get("json")})
        return [{"market": "latam", "region_confirmed": True}]

    monkeypatch.setattr(store, "_request", fake_request)
    result = await store.confirm_region(42, "latam")
    assert result["market"] == "latam"
    assert "region_confirmed=eq.false" in captured["path"]
    assert captured["payload"]["onboarding_complete"] is True


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
