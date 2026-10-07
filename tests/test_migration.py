from pathlib import Path


def test_v9_migration_updates_business_analytics_and_cleans_legacy_jobs():
    sql = Path("V10_MIGRATION_SAFE.sql").read_text(encoding="utf-8").lower()
    assert "create or replace function public.victoria_sales_stats" in sql
    assert "funnel_7d" in sql
    assert "hot_checkout_24h" in sql
    assert "update public.automation_jobs" in sql
    assert "cold_daily" in sql
