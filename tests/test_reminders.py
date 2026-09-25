from datetime import timedelta

from main import reminder_stage_for_inactivity


def test_reminder_stages_follow_d1_d3_d7_schedule() -> None:
    assert reminder_stage_for_inactivity(timedelta(hours=23)) == 0
    assert reminder_stage_for_inactivity(timedelta(hours=24)) == 1
    assert reminder_stage_for_inactivity(timedelta(days=3)) == 2
    assert reminder_stage_for_inactivity(timedelta(days=7)) == 3
