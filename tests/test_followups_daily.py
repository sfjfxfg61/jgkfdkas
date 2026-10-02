from pathlib import Path
import time

from monetization import CHECKOUT_TTL_SECONDS, make_payload, parse_payload
from sales_copy import FOLLOWUPS, followup_text


def test_daily_followups_are_localized_for_every_supported_language():
    langs = {"uk", "ru", "en", "de", "fr", "es"}
    assert langs.issubset(FOLLOWUPS["offer_daily"])
    assert langs.issubset(FOLLOWUPS["checkout_daily"])
    for kind in ["checkout_5m", "checkout_30m", "checkout_3h", "checkout_12h", "checkout_23h"]:
        assert langs.issubset(FOLLOWUPS[kind])


def test_daily_copy_rotates_by_day_seed():
    variants = {followup_text("ru", "checkout_daily", 123, "Рома", day) for day in range(2, 10)}
    assert len(variants) >= 2


def test_new_checkout_payload_really_expires_but_successful_payment_can_still_be_recorded():
    expired = make_payload(12345, "pro", "ua", expires_at=int(time.time()) - 5)
    assert parse_payload(expired, 12345) is None
    parsed = parse_payload(expired, 12345, allow_expired=True)
    assert parsed is not None
    assert parsed[0].code == "pro"
    assert parsed[1] == "ua"


def test_checkout_ttl_is_one_day():
    assert CHECKOUT_TTL_SECONDS == 24 * 60 * 60


def test_runtime_reschedules_daily_followups():
    main = Path("main.py").read_text(encoding="utf-8")
    handlers = Path("handlers.py").read_text(encoding="utf-8")
    assert '"offer_daily"' in main and '"checkout_daily"' in main
    assert 'timedelta(hours=24)' in main
    for kind in ['"checkout_5m"', '"checkout_30m"', '"checkout_3h"', '"checkout_12h"', '"checkout_23h"']:
        assert kind in handlers
    assert 'timedelta(minutes=5)' in handlers
    assert 'timedelta(minutes=30)' in handlers
    assert 'timedelta(hours=3)' in handlers
    assert 'timedelta(hours=12)' in handlers
    assert 'timedelta(hours=24, minutes=5)' in handlers
