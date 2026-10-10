from pathlib import Path

from domain import normalize_partner_code, partner_ref, partner_code_from_ref


def test_partner_code_helpers_and_deep_link_ref_are_safe():
    assert normalize_partner_code("Max-DE") == "max_de"
    assert partner_ref("max_de") == "p_max_de"
    assert partner_code_from_ref("p_max_de") == "max_de"
    assert partner_code_from_ref("threads_de_01") is None


def test_partner_code_rejects_unsafe_or_too_short_values():
    for raw in ("ab", "bad space", "../oops", "x" * 33):
        try:
            normalize_partner_code(raw)
        except ValueError:
            pass
        else:
            raise AssertionError(raw)


def test_v10_migration_is_non_destructive_and_adds_partner_ledger():
    sql = Path("V10_MIGRATION_SAFE.sql").read_text(encoding="utf-8").lower()
    assert "drop table" not in sql
    assert "delete from" not in sql
    assert "create table if not exists public.traffic_partners" in sql
    assert "create table if not exists public.traffic_commissions" in sql
    assert "create table if not exists public.partner_payouts" in sql
    assert "create trigger trg_victoria_partner_commission" in sql
    assert "create or replace function public.victoria_partner_stats" in sql
    assert "on conflict (payment_id) do nothing" in sql


def test_partner_commission_uses_frozen_rate_and_refunds_are_excluded_from_dashboard():
    sql = Path("V10_MIGRATION_SAFE.sql").read_text(encoding="utf-8").lower()
    assert "v_partner.commission_pct" in sql
    assert "commission_pct" in sql
    assert "p.refunded_at is null" in sql


def test_handlers_have_admin_and_self_service_partner_controls():
    handlers = Path("handlers.py").read_text(encoding="utf-8")
    keyboards = Path("keyboards.py").read_text(encoding="utf-8")
    for command in ("partneradd", "partnerinfo", "partnerrate", "partnerpause", "partnerresume", "partnerpay"):
        assert f'Command("{command}")' in handlers
    assert 'Command("partner")' in handlers
    assert 'callback_data="ap:partners"' in keyboards
    assert 'callback_data="partner:self"' in keyboards


def test_existing_user_ref_is_first_touch_and_new_partner_ref_is_validated():
    source = Path("database.py").read_text(encoding="utf-8")
    assert "if not existing:" in source
    assert "partner_code_from_ref(safe_ref)" in source
    assert 'safe_ref = "direct"' in source
