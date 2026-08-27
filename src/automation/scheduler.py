"""
Scheduler Manager Component.
Thread-safe background scheduler handling timers, quiet hours enforcement, restart recovery, and missed run policies.
"""

import datetime
import threading
import time
from typing import Callable
from src.core.config import Config
from src.core.logger import get_logger
from src.automation.models import Automation, AutomationStatus

logger = get_logger()


class SchedulerManager:
    """Manages background scheduled timer callbacks and quiet hours enforcement."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self._lock = threading.RLock()
        self._timers: dict[str, threading.Timer] = {}
        self._running = False


    def is_quiet_hours(self, current_time: datetime.datetime | None = None) -> bool:
        """Check if current time falls within user-configured quiet hours (e.g. 23:00 -> 07:00)."""
        if not self.config.quiet_hours_enabled:
            return False

        now = (current_time or datetime.datetime.now()).time()

        try:
            start_h, start_m = map(int, self.config.quiet_hours_start.split(":"))
            end_h, end_m = map(int, self.config.quiet_hours_end.split(":"))

            start_t = datetime.time(start_h, start_m)
            end_t = datetime.time(end_h, end_m)

            if start_t > end_t:  # Overnight span (e.g. 23:00 -> 07:00)
                return now >= start_t or now <= end_t
            else:
                return start_t <= now <= end_t
        except Exception as e:
            logger.warning(f"Error parsing quiet hours config: {e}")
            return False

    def schedule_automation(self, auto: Automation, callback: Callable[[str], None], delay_sec: float = 1.0) -> None:
        """Schedule a background execution timer callback for an automation rule."""
        with self._lock:
            self.cancel_automation(auto.id)

            if auto.status != AutomationStatus.ACTIVE:
                return

            def _wrapped_callback():
                logger.info(f"SchedulerManager timer fired for automation #{auto.id} ('{auto.name}')")
                callback(auto.id)

            timer = threading.Timer(delay_sec, _wrapped_callback)
            timer.daemon = True
            self._timers[auto.id] = timer
            timer.start()

            auto.next_run_at = (datetime.datetime.now() + datetime.timedelta(seconds=delay_sec)).isoformat()
            logger.info(f"Scheduled automation #{auto.id} for execution in {delay_sec:.1f}s")

    def cancel_automation(self, auto_id: str) -> None:
        """Cancel background timer for an automation ID."""
        with self._lock:
            timer = self._timers.pop(auto_id, None)
            if timer:
                timer.cancel()

    def cancel_all(self) -> None:
        """Emergency stop: cancel all background scheduling timers."""
        with self._lock:
            for auto_id, timer in list(self._timers.items()):
                timer.cancel()
            self._timers.clear()
            logger.warning("SchedulerManager cancelled ALL background scheduled timers.")
