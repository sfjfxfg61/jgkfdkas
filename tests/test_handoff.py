from datetime import datetime, timedelta, timezone

from handlers import _is_hot_lead, _takeover_active


def test_hot_lead_detection_is_multilingual() -> None:
    assert _is_hot_lead("Сколько стоит Pro?")
    assert _is_hot_lead("How can I pay for Ultra?")
    assert _is_hot_lead("¿Cuál es el precio?")
    assert not _is_hot_lead("Привет, как прошёл день?")


def test_takeover_expiration() -> None:
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert _takeover_active({"human_takeover_until": future.isoformat()})
    assert not _takeover_active({"human_takeover_until": past.isoformat()})
    assert not _takeover_active({"human_takeover_until": None})
