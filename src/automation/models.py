"""
Proactive Automation Data Models and Enums.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AutomationStatus(str, Enum):
    """Execution state of an automation rule."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TriggerType(str, Enum):
    """Type of automation trigger mechanism."""

    SCHEDULE = "SCHEDULE"
    INTERVAL = "INTERVAL"
    CONDITION = "CONDITION"
    MANUAL = "MANUAL"


class ConditionType(str, Enum):
    """Type of state evaluation condition."""

    FILE_EXISTS = "FILE_EXISTS"
    FILE_CHANGED = "FILE_CHANGED"
    TIME_REACHED = "TIME_REACHED"
    DATE_REACHED = "DATE_REACHED"
    WEB_CONDITION = "WEB_CONDITION"
    TASK_STATUS = "TASK_STATUS"
    APPLICATION_STATE = "APPLICATION_STATE"


class ActionType(str, Enum):
    """Type of proactive action performed upon trigger."""

    NOTIFY = "NOTIFY"
    RUN_APPROVED_TASK = "RUN_APPROVED_TASK"
    OPEN_APPLICATION = "OPEN_APPLICATION"
    OPEN_FILE = "OPEN_FILE"
    RUN_RESEARCH = "RUN_RESEARCH"


class NotificationPriority(str, Enum):
    """Notification urgency level."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RunStatus(str, Enum):
    """Status of an automation run event."""

    STARTED = "STARTED"
    EVALUATING = "EVALUATING"
    ACTION_PENDING = "ACTION_PENDING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


@dataclass
class Condition:
    """Dataclass representing a condition rule."""

    type: ConditionType
    parameters: dict[str, Any] = field(default_factory=dict)
    operator: str = "EQUALS"
    expected_value: Any = True
    last_evaluated_state: bool | None = None
    last_evaluated_at: str | None = None


@dataclass
class AutomationAction:
    """Dataclass representing a target action to perform upon trigger."""

    type: ActionType
    tool: str = "system_info"
    arguments: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "SAFE"
    requires_confirmation: bool = False


@dataclass
class Notification:
    """Dataclass representing a user notification."""

    id: str
    title: str
    message: str
    type: str = "REMINDER"
    priority: NotificationPriority = NotificationPriority.NORMAL
    source_automation_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    read_at: str | None = None
    status: str = "UNREAD"


@dataclass
class AutomationRun:
    """Dataclass representing an execution run log entry of an automation."""

    id: int | None = None
    automation_id: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    status: RunStatus = RunStatus.STARTED
    result_summary: str = ""
    error_message: str = ""


@dataclass
class AutomationDraft:
    """Unvalidated draft automation proposal parsed from natural language."""

    name: str
    trigger_type: TriggerType
    trigger_config: dict[str, Any]
    action_config: dict[str, Any]
    condition_config: dict[str, Any] | None = None
    description: str = ""


@dataclass
class AutomationResult:
    """Summary result of an automation run execution."""

    automation_id: str
    status: RunStatus
    summary: str
    notification_sent: bool = False
    artifacts: list[Any] = field(default_factory=list)
    error_message: str = ""


@dataclass
class Automation:
    """Dataclass representing a user-configured proactive automation."""

    id: str
    name: str
    description: str = ""
    status: AutomationStatus = AutomationStatus.ACTIVE
    trigger_type: TriggerType = TriggerType.SCHEDULE
    trigger_config: dict[str, Any] = field(default_factory=dict)
    condition: Condition | None = None
    action: AutomationAction | None = None
    permissions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run_at: str | None = None
    next_run_at: str | None = None
    run_count: int = 0
    failure_count: int = 0
