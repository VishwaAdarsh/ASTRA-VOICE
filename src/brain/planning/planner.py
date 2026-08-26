"""
Task Planner Subsystem.
Decomposes user objectives into structured Plan steps.
"""

from src.brain.llm.models import LLMDecision
from src.brain.planning.plan_models import Plan, PlanStep, StepStatus


class TaskPlanner:
    """Generates structured multi-step execution plans."""

    def create_plan_from_decision(self, decision: LLMDecision, objective: str) -> Plan:
        """Create a Plan object from an LLM PLAN decision."""
        steps = []
        for idx, step_dict in enumerate(decision.steps, start=1):
            step = PlanStep(
                step_id=idx,
                tool_name=step_dict.get("tool", step_dict.get("tool_name", "")),
                arguments=step_dict.get("arguments", {}),
                description=step_dict.get("description", f"Step {idx}"),
                status=StepStatus.PENDING,
            )
            steps.append(step)

        return Plan(
            plan_id=f"plan_{int(decision.usage.latency_ms)}",
            objective=objective,
            steps=steps,
        )
