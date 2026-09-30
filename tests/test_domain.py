from datetime import datetime, timedelta, timezone

from domain import compact_text, normalize_lang, normalize_style, premium_is_active, relationship_level


def test_normalization() -> None:
    assert normalize_lang("ru-RU") == "ru"
    assert normalize_lang("de") == "de"
    assert normalize_lang("es-MX") == "es"
    assert normalize_lang("fr-FR") == "fr"
    assert normalize_style("calm") == "calm"
    assert normalize_style("unknown") == "warm"


def test_relationship_levels() -> None:
    assert relationship_level(0)[0] == 1
    assert relationship_level(80)[0] == 2
    assert relationship_level(250)[0] == 3
    assert relationship_level(600)[0] == 4


def test_premium_expiry() -> None:
    now = datetime.now(timezone.utc)
    assert premium_is_active({"is_premium": True, "premium_until": (now + timedelta(days=1)).isoformat()}, now)
    assert not premium_is_active({"is_premium": True, "premium_until": (now - timedelta(seconds=1)).isoformat()}, now)
    assert not premium_is_active({"is_premium": False, "premium_until": (now + timedelta(days=1)).isoformat()}, now)


def test_compact_text() -> None:
    assert compact_text("  hello   world  ") == "hello world"
    assert len(compact_text("x" * 50, 10)) == 10
