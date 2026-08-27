"""
Task Planner Component.
Decomposes high-level user goals into structured, ordered TaskStep plans.
"""

from pathlib import Path
from src.core.config import Config
from src.core.logger import get_logger
from src.task.models import ActionRiskLevel, StepStatus, TaskPlan, TaskStep


logger = get_logger()


class TaskPlanner:
    """Decomposes goals into structured multi-step execution plans."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def generate_plan(self, goal: str) -> TaskPlan:
        """Decompose user goal string into structured TaskPlan."""
        logger.info(f"TaskPlanner generating plan for goal: '{goal}'")
        goal_lower = goal.lower().strip()
        steps: list[TaskStep] = []

        # 1. Goal Pattern: Summarize report / document
        if "summarize" in goal_lower and ("report" in goal_lower or "file" in goal_lower or "doc" in goal_lower):
            steps = [
                TaskStep(
                    step_number=1,
                    description="Search filesystem for target report file",
                    tool_name="search_files",
                    arguments={"query": "report"},
                    expected_result="List of candidate report files",
                    risk_level=ActionRiskLevel.SAFE,
                ),
                TaskStep(
                    step_number=2,
                    description="Read contents of selected report document",
                    tool_name="open_file",
                    arguments={"target": str(Path("README.md").resolve())},
                    expected_result="Text content of report",
                    depends_on=[1],
                    risk_level=ActionRiskLevel.SAFE,
                ),

                TaskStep(
                    step_number=3,
                    description="Generate and save summary text file",
                    tool_name="create_text_file",
                    arguments={"filename": "report_summary.md", "content": "Summary of report content.", "location": "Documents"},
                    expected_result="File created",
                    depends_on=[2],
                    risk_level=ActionRiskLevel.MEDIUM_RISK,
                ),
                TaskStep(
                    step_number=4,
                    description="Verify summary file exists on filesystem",
                    tool_name="file_metadata",
                    arguments={"target": "report_summary.md", "location": "Documents"},
                    expected_result="File metadata verified",
                    depends_on=[3],
                    risk_level=ActionRiskLevel.SAFE,
                ),

            ]
        # 2. Goal Pattern: Research topic online and save notes
        elif "research" in goal_lower or ("search web" in goal_lower and "save" in goal_lower):
            steps = [
                TaskStep(
                    step_number=1,
                    description="Research topic online using web search engine",
                    tool_name="research_topic",
                    arguments={"topic": goal},
                    expected_result="Web research summary and sources",
                    risk_level=ActionRiskLevel.SAFE,
                ),
                TaskStep(
                    step_number=2,
                    description="Save research summary to text file",
                    tool_name="create_text_file",
                    arguments={"file_path": "research_notes.txt", "content": "Research findings..."},
                    expected_result="File created",
                    depends_on=[1],
                    risk_level=ActionRiskLevel.MEDIUM_RISK,
                ),
            ]
        # 3. Goal Pattern: Open app and analyze active window
        elif "open" in goal_lower and "analyze" in goal_lower:
            steps = [
                TaskStep(
                    step_number=1,
                    description="Open target application",
                    tool_name="open_application",
                    arguments={"app_name": "notepad"},
                    expected_result="Application launched",
                    risk_level=ActionRiskLevel.LOW_RISK,
                ),
                TaskStep(
                    step_number=2,
                    description="Analyze active window visual context",
                    tool_name="analyze_active_window",
                    arguments={},
                    expected_result="Visual context description",
                    depends_on=[1],
                    risk_level=ActionRiskLevel.SAFE,
                ),
            ]
        # Fallback Single-Step Default Plan
        else:
            steps = [
                TaskStep(
                    step_number=1,
                    description=f"Process goal: '{goal}'",
                    tool_name="system_info",
                    arguments={},
                    expected_result="System information",
                    risk_level=ActionRiskLevel.SAFE,
                )
            ]

        return TaskPlan(goal=goal, steps=steps, version=1, status="VALIDATED")
