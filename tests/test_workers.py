import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest


@pytest.mark.asyncio
async def test_poll_does_not_ack_update_until_database_commit(monkeypatch):
    import workers

    calls = []
    writes = []
    update = SimpleNamespace(
        update_id=1,
        pre_checkout_query=None,
        model_dump=lambda **_: {"update_id": 1, "message": {"message_id": 1}},
    )

    async def get_updates(**kw):
        calls.append(kw["offset"])
        if len(calls) > 2:
            raise asyncio.CancelledError()
        return [update]

    async def request(*a, **kw):
        writes.append(kw)
        if len(writes) == 1:
            raise RuntimeError("temporary DB failure")

    monkeypatch.setattr(workers.store, "req", request)
    monkeypatch.setattr(workers.asyncio, "sleep", AsyncMock())
    bot = SimpleNamespace(get_updates=get_updates)
    dp = SimpleNamespace(resolve_used_update_types=lambda: [], feed_update=AsyncMock())
    with pytest.raises(asyncio.CancelledError):
        await workers.durable_poll(bot, dp)
    assert calls == [None, None, 2]
    assert writes[-1]["prefer"] == "resolution=ignore-duplicates,return=minimal"


@pytest.mark.asyncio
async def test_only_own_lease_can_be_acknowledged(monkeypatch):
    import workers

    request = AsyncMock()
    monkeypatch.setattr(workers.store, "req", request)
    await workers.finish("automation_jobs", "id", 7, "worker-one", status="sent")
    params = request.call_args.kwargs["params"]
    assert (
        params["locked_by"] == "eq.worker-one" and params["status"] == "eq.processing"
    )


@pytest.mark.asyncio
async def test_revocation_rechecks_access_before_removing_member(monkeypatch):
    import workers

    u = {"user_id": 42, "is_paid": True, "premium_until": "2099-01-01T00:00:00+00:00"}
    monkeypatch.setattr(workers.store, "get_user", AsyncMock(return_value=u))
    monkeypatch.setattr(workers.store, "rpc", AsyncMock(return_value=u))
    bot = SimpleNamespace(ban_chat_member=AsyncMock())
    assert not await workers.send_job(bot, {"user_id": 42, "job_type": "v4_revoke"})
    bot.ban_chat_member.assert_not_awaited()
