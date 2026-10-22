from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from catalog import active, plans, new_payload, parse_invoice, signature, NEW_CODES


def test_signed_invoice_user_amount_duration_and_expiry():
    for code in NEW_CODES:
        p = new_payload(42, code, "ua")
        n = plans("ua")[code].stars
        d = parse_invoice(p, 42, n)
        assert d.code == code and d.days == 30 and len(p.encode()) <= 128
        assert parse_invoice(p, 43, n) is None
        assert parse_invoice(p, 42, n + 1) is None
        assert parse_invoice(p + "X", 42, n) is None
        old = new_payload(42, code, "ua", now=1)
        assert parse_invoice(old, 42, n) is None
        assert parse_invoice(old, 42, n, allow_expired=True).days == 30


def test_legacy_invoices_preserve_original_terms():
    bases = [
        ("simple1:42:forever:400:1:abc", "forever", 400, 36500),
        ("simple2:42:trial:ua:100:1:abc", "trial", 100, 7),
        ("simple3:42:vip:eu:500:1:7201:abc", "vip", 500, 30),
    ]
    for base, code, amount, days in bases:
        d = parse_invoice(base + ":" + signature(base), 42, amount, allow_expired=True)
        assert d and (d.code, d.amount, d.days) == (code, amount, days)


def test_legacy_active_flags_and_expiry():
    assert active({"is_paid": True, "premium_until": None})
    assert active({"is_premium": True, "premium_until": "2099-01-01T00:00:00+00:00"})
    assert not active({"is_paid": True, "premium_until": "2020-01-01T00:00:00+00:00"})


@pytest.mark.asyncio
async def test_plans_clickable_with_prices_without_minting_invoices():
    from main import plans_keyboard

    bot = SimpleNamespace(create_invoice_link=AsyncMock())
    board = await plans_keyboard("ru", "ua", bot, 42)
    assert [r[0].callback_data for r in board.inline_keyboard] == [
        "buy:secret",
        "buy:mistress",
        "buy:daddy",
    ]
    assert ["100", "250", "500"] == [
        r[0].text.split(" · ")[1].split()[0] for r in board.inline_keyboard
    ]
    bot.create_invoice_link.assert_not_awaited()


@pytest.mark.asyncio
async def test_numeric_blog_link_creates_join_request(monkeypatch):
    import main

    monkeypatch.setenv("PUB_LINK_RU", "-1001234567890")
    main._public_cache.clear()
    bot = SimpleNamespace(
        create_chat_invite_link=AsyncMock(
            return_value=SimpleNamespace(invite_link="https://t.me/+test")
        )
    )
    url = await main.public_channel_link(bot, "ru")
    assert url == "https://t.me/+test"
    assert bot.create_chat_invite_link.call_args.kwargs["creates_join_request"] is True
    await main.public_channel_link(bot, "ru")
    assert bot.create_chat_invite_link.await_count == 1


@pytest.mark.asyncio
async def test_precheckout_answer_precedes_any_database(monkeypatch):
    import main

    p = new_payload(42, "secret", "ua")
    order = []

    async def answered(**kw):
        order.append("answer")
        assert kw["ok"]

    async def db(*a, **kw):
        order.append("db")

    monkeypatch.setattr(main.store, "upsert_user", db)
    monkeypatch.setattr(main.store, "event", db)
    q = SimpleNamespace(
        invoice_payload=p,
        from_user=SimpleNamespace(id=42),
        total_amount=100,
        currency="XTR",
        answer=answered,
    )
    await main.confirm_checkout(q, SimpleNamespace())
    assert order[0] == "answer"


@pytest.mark.asyncio
async def test_inbox_registers_once_and_reuses_user_in_handler(monkeypatch):
    import main
    from inbox import InboxMiddleware
    from config import cfg
    from aiogram.types import User

    u = {"user_id": 42, "lang": "ru", "first_name": "Nick"}
    register = AsyncMock(return_value=u)
    monkeypatch.setattr(main.store, "upsert_user", register)
    monkeypatch.setattr(main.store, "message", AsyncMock(return_value=[{"id": 1}]))
    monkeypatch.setattr(main.store, "ticket", AsyncMock())
    monkeypatch.setattr(main.store, "event", AsyncMock())
    tg = User(id=42, is_bot=False, first_name="Nick", language_code="ru")
    event = SimpleNamespace(
        from_user=tg,
        chat=SimpleNamespace(type="private", id=42),
        text="hello",
        caption=None,
        successful_payment=None,
        refunded_payment=None,
        content_type="text",
        message_id=3,
    )
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=4)),
        copy_message=AsyncMock(),
    )

    async def handler(event, data):
        assert await main.reg(tg) == u

    await InboxMiddleware(main.store, cfg)(handler, event, {"bot": bot})
    register.assert_awaited_once()
    assert "🌐 ru" in bot.send_message.call_args.args[1]


@pytest.mark.asyncio
async def test_manual_offer_sends_one_bound_payment_button_and_checks_admin(
    monkeypatch,
):
    import main

    draft = {
        "user_id": 42,
        "plan": "mistress",
        "amount": 333,
        "body": "Личное предложение",
    }
    user = {"user_id": 42, "lang": "ru", "market": "eu", "first_name": "Nick"}
    get_draft = AsyncMock(return_value=draft)
    monkeypatch.setattr(main, "get_draft", get_draft)
    monkeypatch.setattr(main.store, "get_user", AsyncMock(return_value=user))
    for key in ("message", "event", "req"):
        monkeypatch.setattr(main.store, key, AsyncMock())
    bot = SimpleNamespace(
        create_invoice_link=AsyncMock(return_value="https://t.me/$offer"),
        send_message=AsyncMock(),
    )
    c = SimpleNamespace(
        from_user=SimpleNamespace(id=main.cfg.admin_id + 1),
        data="offer:send",
        answer=AsyncMock(),
        message=SimpleNamespace(answer=AsyncMock()),
    )
    await main.offer_action(c, bot)
    get_draft.assert_not_awaited()
    bot.send_message.assert_not_awaited()
    c.from_user.id = main.cfg.admin_id
    await main.offer_action(c, bot)
    send = bot.send_message.call_args
    assert send.args == (42, "Личное предложение")
    rows = send.kwargs["reply_markup"].inline_keyboard
    assert len(rows) == 1 and len(rows[0]) == 1 and "333" in rows[0][0].text
    invoice = bot.create_invoice_link.call_args.kwargs
    assert parse_invoice(invoice["payload"], 42, 333).code == "mistress"


@pytest.mark.asyncio
async def test_unknown_telegram_language_prompts_selection(monkeypatch):
    import main

    user = {"user_id": 42, "lang": "en", "language_selected": False}
    monkeypatch.setattr(main, "reg", AsyncMock(return_value=user))
    monkeypatch.setattr(main.store, "rpc", AsyncMock())
    monkeypatch.setattr(main.store, "event", AsyncMock())
    send_home = AsyncMock()
    monkeypatch.setattr(main, "send_home", send_home)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=42, language_code="ja"),
        text="/start",
        answer=AsyncMock(),
    )
    await main.start(message, SimpleNamespace())
    board = message.answer.call_args.kwargs["reply_markup"]
    assert sum(map(len, board.inline_keyboard)) == 8
    send_home.assert_not_awaited()
