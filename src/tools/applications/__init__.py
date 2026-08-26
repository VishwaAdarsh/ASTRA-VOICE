"""
ASTRA Applications Subsystem Package (Phase 5).
"""

from src.tools.applications.aliases import ApplicationRegistry
from src.tools.applications.launcher import OpenApplicationTool
from src.tools.applications.lifecycle import CloseApplicationTool
from src.tools.applications.projects import OpenProjectTool, ProjectRegistry
from src.tools.applications.status import ApplicationStatusTool

__all__ = [
    "ApplicationRegistry",
    "ApplicationStatusTool",
    "CloseApplicationTool",
    "OpenApplicationTool",
    "OpenProjectTool",
    "ProjectRegistry",
]
