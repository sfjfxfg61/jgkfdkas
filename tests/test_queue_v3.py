from pathlib import Path


def test_worker_claims_jobs_atomically():
    main = Path("main.py").read_text(encoding="utf-8")
    db = Path("database.py").read_text(encoding="utf-8")
    assert "claim_due_jobs" in main
    assert "rpc/claim_due_automation_jobs" in db
    assert "claim_due_automation_jobs" in db
    assert "locked_at" in db and "locked_by" in db


def test_admin_panel_exists():
    keyboards = Path("keyboards.py").read_text(encoding="utf-8")
    handlers = Path("handlers.py").read_text(encoding="utf-8")
    assert "admin_panel_kb" in keyboards
    assert 'callback_data="ap:stats"' in keyboards
    assert 'callback_data="ap:jobs"' in keyboards
    assert 'F.data.startswith("ap:")' in handlers
