import pytest

from database import SupabaseStore


@pytest.mark.asyncio
async def test_proactive_query_uses_postgrest_safe_utc_timestamp(monkeypatch) -> None:
    captured: dict[str, str] = {}
    store = SupabaseStore()

    async def fake_request(method: str, path: str, **_: object) -> list[dict]:
        captured["method"] = method
        captured["path"] = path
        return []

    monkeypatch.setattr(store, "_request", fake_request)
    assert await store.eligible_for_proactive() == []
    assert captured["method"] == "GET"
    assert "+00:00" not in captured["path"]
    assert "premium_until=gt." in captured["path"]
    assert "Z" in captured["path"]
