from pathlib import Path

from monetization import PRICE_MATRIX
from sales_copy import FOLLOWUPS


def test_v9_has_no_generic_cold_nudge_in_limited_scheduler():
    source = Path("handlers.py").read_text(encoding="utf-8")
    start = source.index("async def _schedule_cold_followups")
    end = source.index("async def _show_gate_message", start)
    block = source[start:end]
    assert 'if settings.marketing_mode == "limited":\n        return' in block


def test_v9_checkout_rescue_is_ten_minutes():
    source = Path("handlers.py").read_text(encoding="utf-8")
    assert '"checkout_10m", (now + timedelta(minutes=10))' in source
    assert '"buyer_checkin_10m"' in source


def test_v9_post_purchase_checkin_exists_on_all_languages():
    bank = FOLLOWUPS["buyer_checkin_10m"]
    assert set(bank) >= {"uk", "ru", "en", "de", "fr", "es"}
    assert all(bank[x] for x in ("uk", "ru", "en", "de", "fr", "es"))


def test_v9_offer_recommends_middle_plan_without_fake_scarcity():
    text = FOLLOWUPS["offer_3h"]["en"][0].lower()
    assert "channel + chat" in text
    assert "only today" not in text
    assert "last chance" not in text


def test_v9_checkout_admin_hot_lead_alert_and_action_keyboard():
    main = Path("main.py").read_text(encoding="utf-8")
    handlers = Path("handlers.py").read_text(encoding="utf-8")
    assert "Горячий лид не завершил оплату за 10 минут" in main
    assert "keyboards.admin_ticket_kb(user_id)" in main
    assert "ГОРЯЧИЙ ЛИД · клик по оплате" in handlers


def test_v9_stats_migration_is_non_destructive():
    sql = Path("V10_MIGRATION_SAFE.sql").read_text(encoding="utf-8").lower()
    assert "drop table" not in sql
    assert "delete from" not in sql
    assert "create or replace function public.victoria_sales_stats" in sql
    assert "cold_daily" in sql and "cancelled by victoria v10 migration" in sql


def test_prices_stay_in_agreed_ranges():
    low = {"ua", "cis", "latam", "asia"}
    high = {"eu", "us", "global"}
    for market in low:
        assert PRICE_MATRIX[market] == {"plus":150,"pro":350,"ultra":750,"black":2500}
    for market in high:
        assert PRICE_MATRIX[market] == {"plus":250,"pro":500,"ultra":1000,"black":2500}
