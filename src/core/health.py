"""
ASTRA Subsystem Health Manager.
Monitors operational health across 9 core subsystems (STT, TTS, LLM, Vision, OCR, Web, Database, Scheduler, TaskEngine).
"""

from dataclasses import dataclass, field
from enum import Enum
from src.core.config import Config
from src.core.logger import get_logger

logger = get_logger()


class HealthStatus(str, Enum):
    """Subsystem operational health state."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class SubsystemHealth:
    """Operational status container for a single subsystem."""

    name: str
    status: HealthStatus = HealthStatus.HEALTHY
    message: str = "Operating normally"
    last_checked: str = ""


class HealthManager:
    """Tracks and reports health diagnostics for all ASTRA subsystems."""

    SUBSYSTEMS = [
        "STT",
        "TTS",
        "LLM",
        "Vision",
        "OCR",
        "Web",
        "Database",
        "Scheduler",
        "TaskEngine",
    ]

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self._health: dict[str, SubsystemHealth] = {
            sub: SubsystemHealth(name=sub, status=HealthStatus.HEALTHY) for sub in self.SUBSYSTEMS
        }

    def set_status(self, name: str, status: HealthStatus, message: str = "") -> None:
        """Update health status for a specific subsystem."""
        if name in self._health:
            self._health[name].status = status
            self._health[name].message = message or f"Status updated to {status.value}"
            logger.info(f"HealthManager [{name}]: {status.value} - {self._health[name].message}")

    def get_status(self, name: str) -> SubsystemHealth | None:
        """Get current health status for a subsystem."""
        return self._health.get(name)

    def get_all_health(self) -> dict[str, SubsystemHealth]:
        """Get complete health status map for all subsystems."""
        return self._health.copy()

    def get_health_status(self) -> dict[str, SubsystemHealth]:
        """Get complete health status map for all subsystems."""
        return self.get_all_health()


    def is_overall_healthy(self) -> bool:
        """Check if all subsystems are operational without UNAVAILABLE critical failures."""
        return all(h.status != HealthStatus.UNAVAILABLE for h in self._health.values())
