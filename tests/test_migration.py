from pathlib import Path


def test_migration_contains_operational_objects():
    sql = Path("MIGRATION_RUN_FIRST.sql").read_text(encoding="utf-8")
    for item in [
        "public_channel_member",
        "automation_jobs",
        "record_chat_activity",
        "record_payment_and_activate",
        "request_paid_call",
        "victoria_sales_stats",
    ]:
        assert item in sql
