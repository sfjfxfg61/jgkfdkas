from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest


@pytest.mark.asyncio
async def test_personal_followup_uses_escaped_first_name(monkeypatch):
    import workers

    monkeypatch.setattr(
        workers.store,
        "get_user",
        AsyncMock(
            return_value={
                "user_id": 42,
                "first_name": "Илля <3",
                "username": "not_this",
                "lang": "ru",
            }
        ),
    )
    monkeypatch.setattr(workers.store, "event", AsyncMock())
    bot = SimpleNamespace(send_message=AsyncMock())
    await workers.send_job(bot, {"id": 1, "user_id": 42, "job_type": "v4_followup"})
    text = bot.send_message.call_args.args[1]
    assert "Илля &lt;3" in text and "not_this" not in text


@pytest.mark.asyncio
async def test_vip_offer_has_only_one_button(monkeypatch):
    import workers

    u = {"user_id": 42, "lang": "ru", "market": "eu", "first_name": "Nick"}
    for key in ("req", "patch", "event"):
        monkeypatch.setattr(workers.store, key, AsyncMock())
    monkeypatch.setattr(workers.store, "get_user", AsyncMock(return_value=u))
    bot = SimpleNamespace(
        send_message=AsyncMock(),
        create_invoice_link=AsyncMock(return_value="https://t.me/$invoice"),
    )
    await workers.send_job(
        bot, {"id": 1, "user_id": 42, "job_type": "v4_daily", "payload": {}}
    )
    args = bot.send_message.call_args
    assert "скидку на пару часов" in args.args[1]
    rows = args.kwargs["reply_markup"].inline_keyboard
    assert (
        len(rows) == 1
        and len(rows[0]) == 1
        and "🥺" in rows[0][0].text
        and "500" in rows[0][0].text
    )


@pytest.mark.asyncio
async def test_paused_and_blocked_users_not_messaged(monkeypatch):
    import workers

    bot = SimpleNamespace(send_message=AsyncMock())
    for flag in ("blocked", "automation_paused"):
        monkeypatch.setattr(
            workers.store,
            "get_user",
            AsyncMock(return_value={"user_id": 42, flag: True}),
        )
        assert not await workers.send_job(bot, {"user_id": 42, "job_type": "v4_daily"})
    bot.send_message.assert_not_awaited()
