"""
Research Topic Tool.
Executes multi-source web research tasks and constructs source-attributed answers.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.web.research.researcher import WebResearcher

logger = get_logger()


class ResearchTopicTool(BaseTool):
    """Tool to perform multi-source research on a topic."""

    def __init__(self, config: Config | None = None, researcher: WebResearcher | None = None):
        self.config = config or Config()
        self.researcher = researcher or WebResearcher(config=self.config)

    @property
    def name(self) -> str:
        return "research_topic"

    @property
    def description(self) -> str:
        return "Performs multi-source web research on a topic and provides synthesized answers with source citations."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "topic" in parameters and isinstance(parameters["topic"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        topic = str(parameters["topic"]).strip()
        depth = str(parameters.get("depth", "STANDARD")).upper()

        try:
            answer = self.researcher.research(topic, depth=depth)
            sources_data = [
                {
                    "id": s.id,
                    "title": s.title,
                    "url": s.url,
                    "domain": s.domain,
                }
                for s in answer.sources
            ]

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=answer.summary,
                data={
                    "summary": answer.summary,
                    "key_points": answer.key_points,
                    "sources": sources_data,
                },
            )
        except Exception as e:
            logger.error(f"ResearchTopicTool failed for '{topic}': {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Research task failed: {e}",
                error=str(e),
            )
