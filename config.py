"""Deployment configuration. Never store secrets in source control."""
from __future__ import annotations
import base64
import json
import os
from dataclasses import dataclass


def _boolean(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower().strip() in {"true", "1", "yes", "on"}


def _role(key: str) -> str:
    try:
        data = key.split('.')[1]
        data += '=' * (-len(data) % 4)
        return str(json.loads(base64.urlsafe_b64decode(data)).get('role') or '')
    except (ValueError, IndexError, UnicodeError, TypeError):
        return ''


@dataclass(frozen=True)
class Config:
    token: str = os.getenv('BOT_TOKEN', '').strip()
    admin_id: int = int(os.getenv('ADMIN_ID', '0') or 0)
    db_url: str = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    db_key: str = (os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY') or '').strip()
    private_id: int = int(os.getenv('PRIVATE_CHANNEL_ID') or os.getenv('PRIVATE_CHANNEL_URL') or '0')
    port: int = int(os.getenv('PORT', '8080'))
    signing_key: str = (os.getenv('INVOICE_SIGNING_KEY') or os.getenv('BOT_TOKEN') or '').strip()
    vip_days: int = int(os.getenv('VIP_DAYS', '30'))
    # JSON override: {"ua":{"trial":100,"forever":250,"vip":500}, ...}
    price_matrix_json: str = os.getenv('PRICE_MATRIX_JSON', '').strip()
    followups: bool = _boolean('FOLLOWUPS_ENABLED', True)
    reminder_timezone: str = os.getenv('REMINDER_TIMEZONE', 'Europe/Kyiv').strip()
    remove_expired: bool = _boolean('REMOVE_EXPIRED', True)
    # Daily messages go to users who started the bot and did not turn them off.
    reminder_window_start: str = os.getenv('REMINDER_WINDOW_START', '18:00').strip()
    reminder_window_end: str = os.getenv('REMINDER_WINDOW_END', '21:00').strip()

    def public_for(self, lang: str) -> str:
        return os.getenv('PUB_LINK_' + lang.upper(), '').strip()


    def validate(self):
        missing = [key for key, ok in {
            'BOT_TOKEN': bool(self.token), 'ADMIN_ID': self.admin_id > 0,
            'SUPABASE_URL': self.db_url.startswith('https://'),
            'SUPABASE_KEY': bool(self.db_key), 'PRIVATE_CHANNEL_URL': self.private_id < 0,
        }.items() if not ok]
        if missing:
            raise RuntimeError('Missing/invalid configuration: ' + ', '.join(missing))
        if self.db_key.startswith('sb_publishable_') or _role(self.db_key) in ('anon', 'authenticated'):
            raise RuntimeError('Use Supabase service_role or sb_secret key, not a public key')
        for key, clock in [('REMINDER_WINDOW_START', self.reminder_window_start),
                           ('REMINDER_WINDOW_END', self.reminder_window_end)]:
            try:
                hour, minute = map(int, clock.split(':'))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError('clock out of range')
            except Exception as exc:
                raise RuntimeError(key + ' must be HH:MM') from exc
        if self.reminder_window_end <= self.reminder_window_start:
            raise RuntimeError('REMINDER_WINDOW_END must be after start on the same day')
        if self.vip_days < 1:
            raise RuntimeError('VIP_DAYS must be >= 1')
        if self.price_matrix_json:
            try:
                pricing = json.loads(self.price_matrix_json)
                if not isinstance(pricing, dict):
                    raise ValueError('Price matrix must be a JSON object')
                for market, choices in pricing.items():
                    if market not in ('ua', 'cis', 'latam', 'asia', 'eu', 'us', 'global'):
                        raise ValueError('Unknown market: ' + str(market))
                    if not isinstance(choices, dict) or set(choices) != {'trial', 'forever', 'vip'}:
                        raise ValueError('Every market override requires trial/forever/vip')
                    if any(type(v) is not int or v < 1 or v > 10000 for v in choices.values()):
                        raise ValueError('Each Star price must be 1..10000')
            except (ValueError, TypeError) as exc:
                raise RuntimeError('PRICE_MATRIX_JSON invalid') from exc


cfg = Config()
