from pathlib import Path

from sales_copy import FOLLOWUPS


def test_cold_reactivation_has_all_languages():
    langs = {"uk", "ru", "en", "de", "fr", "es"}
    for kind in ["cold_6h", "cold_24h", "cold_daily"]:
        assert kind in FOLLOWUPS
        assert langs.issubset(FOLLOWUPS[kind])
        assert all(FOLLOWUPS[kind][lang] for lang in langs)


def test_global_reactivation_is_wired_into_runtime():
    main = Path("main.py").read_text(encoding="utf-8")
    handlers = Path("handlers.py").read_text(encoding="utf-8")
    db = Path("database.py").read_text(encoding="utf-8")
    assert "global_reactivation_seed_loop" in main
    assert '"cold_daily"' in main
    assert "reactivation_candidates" in db
    assert "COLD_JOB_TYPES" in handlers
    assert "_schedule_cold_followups" in handlers
