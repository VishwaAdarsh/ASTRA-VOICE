"""
ASTRA Proactive Personal Assistant & Intelligent Automation Subsystem Package (Phase 10).
"""

from src.automation.evaluator import ConditionEvaluator
from src.automation.manager import AutomationManager
from src.automation.models import (
    ActionType,
    Automation,
    AutomationAction,
    AutomationDraft,
    AutomationResult,
    AutomationRun,
    AutomationStatus,
    Condition,
    ConditionType,
    Notification,
    NotificationPriority,
    RunStatus,
    TriggerType,
)
from src.automation.notification import NotificationManager
from src.automation.parser import AutomationParser
from src.automation.repository import AutomationRepository
from src.automation.scheduler import SchedulerManager
from src.automation.validator import AutomationValidator

__all__ = [
    "ActionType",
    "Automation",
    "AutomationAction",
    "AutomationDraft",
    "AutomationManager",
    "AutomationParser",
    "AutomationRepository",
    "AutomationResult",
    "AutomationRun",
    "AutomationStatus",
    "AutomationValidator",
    "Condition",
    "ConditionEvaluator",
    "ConditionType",
    "Notification",
    "NotificationManager",
    "NotificationPriority",
    "RunStatus",
    "SchedulerManager",
    "TriggerType",
]
