"""
Search Web Tool.
Searches the web using SearchProviderFactory and returns structured results.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.web.models import SearchRequest
from src.web.search.factory import SearchProviderFactory
from src.web.search.provider import SearchProvider

logger = get_logger()


class SearchWebTool(BaseTool):
    """Tool to perform internet searches."""

    def __init__(self, config: Config | None = None, provider: SearchProvider | None = None):
        self.config = config or Config()
        self.provider = provider or SearchProviderFactory.create(self.config)

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "Searches the internet for information on a query."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "query" in parameters and isinstance(parameters["query"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        query = str(parameters["query"]).strip()
        limit = int(parameters.get("limit", 5))

        try:
            req = SearchRequest(query=query, limit=limit)
            results = self.provider.search(req)

            data_results = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "domain": r.domain,
                }
                for r in results
            ]

            msg = f"Found {len(results)} web search results for '{query}'."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={"results": data_results, "count": len(results)},
            )
        except Exception as e:
            logger.error(f"SearchWebTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Web search failed: {e}",
                error=str(e),
            )
