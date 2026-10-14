import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from catalog import PERPETUAL, active, entitlement, new_payload, parse_payload, plans
from storage import Store


def test_payload_integrity_and_bound_user():
    token = new_payload(42, 'trial')
    assert parse_payload(token, 42, plans()['trial'].stars) == 'trial'
    assert parse_payload(token, 43, plans()['trial'].stars) is None
    assert parse_payload(token, 42, plans()['trial'].stars + 1) is None
    assert parse_payload(token[:-1] + ('a' if token[-1] != 'a' else 'b'), 42, plans()['trial'].stars) is None


def test_payload_expiry():
    token = new_payload(42, 'trial', now=1)
    assert parse_payload(token, 42, plans()['trial'].stars) is None
    assert parse_payload(token, 42, plans()['trial'].stars, allow_expired=True) == 'trial'


def test_legacy_lifetime_and_active():
    old = {'is_paid': True, 'is_premium': True, 'premium_until': '2099-12-31T23:59:59+00:00'}
    assert active(old)
    assert entitlement(old, 'forever') == PERPETUAL
    assert active({'is_paid': True, 'is_premium': False, 'premium_until': None})
    assert not active({'is_paid': False, 'is_premium': False, 'premium_until': '2099-12-31T23:59:59+00:00'})
    assert not active({'is_paid': True, 'premium_until': '2020-01-01T00:00:00+00:00'})


def test_trials_extend_valid_time():
    d = datetime(2026, 10, 13, tzinfo=timezone.utc)
    u = {'premium_until': (d + timedelta(days=3)).isoformat()}
    assert entitlement(u, 'trial', now=d) == d + timedelta(days=10)
    assert entitlement(None, 'trial', now=d) == d + timedelta(days=7)


@pytest.mark.asyncio
async def test_ensure_existing_user_does_not_reset_paid_flags():
    s = Store()
    old = {'user_id': 42, 'is_paid': True, 'is_premium': True, 'premium_until': '2099-12-31T23:59:59+00:00'}
    seen = {}
    async def getter(uid):
        assert uid == 42
        return old
    async def request(method, table, *, params=None, body=None, prefer=None):
        seen.update(body)
        return [old]
    s.get_user = getter
    s.req = request
    tg = SimpleNamespace(id=42, first_name='Joe', username='j')
    await s.upsert_user(tg, 'en')
    assert 'is_paid' not in seen
    assert 'is_premium' not in seen
    assert 'premium_until' not in seen
    assert 'subscription_tier' not in seen
    assert 'ref' not in seen


def test_market_pricing_and_signed_region_amount():
    from catalog import default_market, matrix, parse_invoice
    assert default_market('uk') == 'ua'
    assert default_market('de') == 'eu'
    assert matrix()['ua'] == {'trial': 100, 'forever': 250, 'vip': 500}
    assert matrix()['eu'] == {'trial': 250, 'forever': 500, 'vip': 1000}
    p = new_payload(42, 'vip', 'ua')
    result = parse_invoice(p, 42, 500)
    assert result is not None and (result.code, result.market, result.amount) == ('vip', 'ua', 500)
    assert parse_invoice(p, 42, 1000) is None
    assert parse_invoice(p, 43, 500) is None


def test_previous_simple1_invoice_still_parses():
    from catalog import signature, parse_invoice
    base = 'simple1:42:forever:400:1790000000:1a2b3c4d'
    token = base + ':' + signature(base)
    result = parse_invoice(token, 42, 400, allow_expired=True)
    assert result and result.code == 'forever'
    assert result.amount == 400


@pytest.mark.asyncio
async def test_direct_payment_buttons_and_callback_fallback():
    pytest.importorskip("aiogram", reason="aiogram is installed on Render, not this offline testing runtime")
    from main import plans_keyboard
    class BotStub:
        def __init__(self, fail=False):
            self.called = []
            self.fail = fail
        async def create_invoice_link(self, **kw):
            self.called.append(kw)
            if self.fail:
                raise RuntimeError('Telegram did not create link')
            return 'https://t.me/$' + str(len(self.called))
    bot = BotStub()
    board = await plans_keyboard('uk', 'ua', bot, 42)
    assert len(bot.called) == 3
    assert [kw['prices'][0].amount for kw in bot.called] == [100, 250, 500]
    assert all(btn[0].url and btn[0].url.startswith('https://t.me/') for btn in board.inline_keyboard[:3])
    assert len({kw['payload'] for kw in bot.called}) == 3
    fallback = await plans_keyboard('en', 'eu', BotStub(fail=True), 42)
    assert [r[0].callback_data for r in fallback.inline_keyboard[:3]] == ['buy:trial', 'buy:forever', 'buy:vip']


def test_agreed_reminder_copy_and_schedule():
    from config import cfg
    from words import t
    assert cfg.reminder_window_start == '18:00'
    assert cfg.reminder_window_end == '21:00'
    assert cfg.reminder_timezone == 'Europe/Kyiv'
    assert 'Условия доступа могут измениться' in t('ru', 'reminder')
    assert 'могут измениться' in t('ru', 'reminder')
