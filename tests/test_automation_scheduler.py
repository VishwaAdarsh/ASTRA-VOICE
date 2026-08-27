"""
Unit tests for SchedulerManager and quiet hours.
"""

import datetime
from src.core.config import Config
from src.automation.scheduler import SchedulerManager


def test_scheduler_quiet_hours_overnight():
    cfg = Config()
    cfg.quiet_hours_enabled = True
    cfg.quiet_hours_start = "23:00"
    cfg.quiet_hours_end = "07:00"

    scheduler = SchedulerManager(config=cfg)

    # 1:30 AM -> Quiet Hours True
    night_time = datetime.datetime(2026, 8, 27, 1, 30)
    assert scheduler.is_quiet_hours(current_time=night_time) == True

    # 2:00 PM -> Quiet Hours False
    day_time = datetime.datetime(2026, 8, 27, 14, 0)
    assert scheduler.is_quiet_hours(current_time=day_time) == False
