from datetime import datetime, timedelta, timezone

from domain import compact_text, normalize_lang, premium_is_active


def test_normalization_and_compaction():
    assert normalize_lang("uk-UA") == "uk"
    assert normalize_lang("xx") == "en"
    assert compact_text("  hello   world  ") == "hello world"


def test_premium_active():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert premium_is_active({"is_premium": True, "premium_until": future})
    assert not premium_is_active({"is_premium": True, "premium_until": past})
