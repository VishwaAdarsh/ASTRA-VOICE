"""
Task Engine Enums, Data Models, and Dataclasses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Execution status of an autonomous task."""

    CREATED = "CREATED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    REPLANNING = "REPLANNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Execution status of a single task step."""

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class AutonomyLevel(str, Enum):
    """Configurable autonomy level."""

    LEVEL_0 = "LEVEL_0"  # Manual
    LEVEL_1 = "LEVEL_1"  # Suggest
    LEVEL_2 = "LEVEL_2"  # Auto Safe Actions
    LEVEL_3 = "LEVEL_3"  # Multi-step Workflows
    LEVEL_4 = "LEVEL_4"  # Controlled Advanced Autonomy


class ActionRiskLevel(str, Enum):
    """Action risk classification for confirmation gating."""

    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    DESTRUCTIVE = "DESTRUCTIVE"


class FailureType(str, Enum):
    """Classification of task failure."""

    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    PERMISSION = "PERMISSION"
    VALIDATION = "VALIDATION"
    SECURITY = "SECURITY"
    RESOURCE = "RESOURCE"
    UNKNOWN = "UNKNOWN"


@dataclass
class TaskStep:
    """Dataclass representing a single executable step within a task plan."""

    step_number: int
    description: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    expected_result: str = ""
    status: StepStatus = StepStatus.PENDING
    result_data: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    depends_on: list[int] = field(default_factory=list)
    risk_level: ActionRiskLevel = ActionRiskLevel.SAFE


@dataclass
class TaskPlan:
    """Dataclass representing a validated task plan."""

    goal: str
    steps: list[TaskStep] = field(default_factory=list)
    version: int = 1
    status: str = "VALIDATED"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class VerificationResult:
    """Outcome of step verification."""

    success: bool
    method: str
    evidence: str = ""
    message: str = ""


@dataclass
class TaskArtifact:
    """Record of a created or modified file/output produced by a task."""

    name: str
    file_path: str
    type: str = "FILE"  # FILE, SUMMARY, IMAGE, CONTEXT


@dataclass
class TaskCheckpoint:
    """Checkpoint snapshot for crash recovery and state resumption."""

    task_id: str
    step_number: int
    state_json: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    safe_to_resume: bool = True


@dataclass
class TaskResult:
    """Final summary outcome of task execution."""

    task_id: str
    status: TaskStatus
    summary: str
    completed_steps: int
    total_steps: int
    artifacts: list[TaskArtifact] = field(default_factory=list)
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class Task:
    """Dataclass representing a full autonomous task."""

    id: str
    goal: str
    status: TaskStatus = TaskStatus.CREATED
    autonomy_level: AutonomyLevel = AutonomyLevel.LEVEL_3
    plan: TaskPlan | None = None
    current_step_index: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    result_summary: str = ""
    error_message: str = ""
    artifacts: list[TaskArtifact] = field(default_factory=list)
