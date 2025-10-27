from datetime import datetime, time

from app.jobs.scheduler import QuietHours


def test_quiet_hours_blocks_time_range():
    quiet = QuietHours(start=time(21, 0), end=time(8, 0))

    assert quiet.allows(datetime(2024, 1, 1, 10, 0)) is True
    assert quiet.allows(datetime(2024, 1, 1, 22, 0)) is False
    assert quiet.allows(datetime(2024, 1, 2, 7, 30)) is False
