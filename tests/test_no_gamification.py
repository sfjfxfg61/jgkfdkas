from pathlib import Path


def test_runtime_has_no_memory_or_relationship_system():
    runtime = "\n".join(
        Path(name).read_text(encoding="utf-8")
        for name in ["handlers.py", "main.py", "database.py", "domain.py"]
    ).lower()
    assert "relationship_level" not in runtime
    assert "extract_memor" not in runtime
    assert "upsert_memor" not in runtime
    assert "xp +" not in runtime


def test_migration_does_not_increment_xp():
    sql = Path("MIGRATION_RUN_FIRST.sql").read_text(encoding="utf-8").lower()
    assert "xp = xp +" not in sql
    assert "record_chat_activity" in sql
