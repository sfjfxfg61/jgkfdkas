import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from reminder_schedule import daily_slot, should_send_today
from config import cfg


def test_daily_time_spread_and_stability():
    local_date = datetime(2026, 10, 13).date()
    slots = [daily_slot(uid, local_date, '18:00', '21:00') for uid in range(1, 125)]
    assert all(18 * 60 <= s < 21 * 60 for s in slots)
    assert len(set(slots)) > 50
    assert daily_slot(1, local_date, '18:00', '21:00') == daily_slot(1, local_date, '18:00', '21:00')
    assert daily_slot(1, local_date, '18:00', '21:00') != daily_slot(1, local_date + timedelta(days=1), '18:00', '21:00')


def test_catch_up_and_one_send_per_day():
    local = ZoneInfo('Europe/Kyiv')
    user = {'user_id': 42, 'blocked': False, 'automation_paused': False, 'last_reminder_at': None}
    at_end = datetime(2026, 10, 13, 22, 10, tzinfo=local)
    assert should_send_today(user, at_end, 'Europe/Kyiv', '18:00', '21:00')
    user['last_reminder_at'] = at_end.astimezone(timezone.utc).isoformat()
    assert not should_send_today(user, at_end, 'Europe/Kyiv', '18:00', '21:00')
    assert should_send_today(user, at_end + timedelta(days=1), 'Europe/Kyiv', '18:00', '21:00')


def test_optout_blocks_reminder():
    user = {'user_id': 42, 'blocked': False, 'automation_paused': True, 'last_reminder_at': None}
    assert not should_send_today(user, datetime(2026, 10, 13, 22, tzinfo=ZoneInfo('Europe/Kyiv')),
                                 'Europe/Kyiv', '18:00', '21:00')
    user['automation_paused'] = False
    user['blocked'] = True
    assert not should_send_today(user, datetime(2026, 10, 13, 22, tzinfo=ZoneInfo('Europe/Kyiv')),
                                 'Europe/Kyiv', '18:00', '21:00')


def test_channel_env_uses_existing_keys(monkeypatch):
    monkeypatch.setenv('PUB_LINK_UK', '-1001234567890')
    assert cfg.public_for('uk') == '-1001234567890'


def test_paid_users_not_excluded_from_reminder_loop():
    source=(Path(__file__).resolve().parents[1]/'main.py').read_text(encoding='utf8')
    start=source.index('async def reminders_loop(bot: Bot):')
    end=source.index('async def expiry_loop(bot: Bot):', start)
    reminder_body=source[start:end]
    assert 'if active(u):' not in reminder_body
    assert 'if not should_send_today(u, local,' in reminder_body

def test_admin_reminder_count_includes_paid():
    source=(Path(__file__).resolve().parents[1]/'main.py').read_text(encoding='utf8')
    start=source.index('async def admin_reminder_stats(')
    end=source.index("@router.message(Command('payments'))", start)
    stats_body=source[start:end]
    assert 'and not active(u)' not in stats_body
    assert 'включая Premium' in stats_body
