"""Spread once-daily member notifications across a local-time window.

Keeps no in-memory send queue and catches up on missed schedules after restarts.
"""
from datetime import date, datetime, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo


def clock_minutes(clock: str) -> int:
    hh, mm = map(int, clock.split(':'))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError('invalid clock')
    return hh * 60 + mm


def daily_slot(user_id: int, local_day: date, start: str, end: str) -> int:
    lower, upper = clock_minutes(start), clock_minutes(end)
    if lower >= upper:
        raise ValueError('start must precede end')
    digest = sha256(f'{user_id}:{local_day.isoformat()}:Victoria:v3'.encode()).digest()
    return lower + int.from_bytes(digest[:8], 'big') % (upper - lower)


def should_send_today(user: dict, now: datetime, tz: str, start: str, end: str) -> bool:
    if user.get('blocked') or user.get('automation_paused'):
        return False
    if not user.get('user_id'):
        return False
    local = now.astimezone(ZoneInfo(tz))
    last = user.get('last_reminder_at')
    if last:
        try:
            prior = datetime.fromisoformat(str(last).replace('Z', '+00:00'))
            if prior.tzinfo is None:
                prior = prior.replace(tzinfo=timezone.utc)
            if prior.astimezone(ZoneInfo(tz)).date() >= local.date():
                return False
        except (TypeError, ValueError):
            pass
    minute_now = local.hour * 60 + local.minute
    return minute_now >= daily_slot(int(user['user_id']), local.date(), start, end)
