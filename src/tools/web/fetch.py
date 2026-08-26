"""
Fetch Webpage Tool.
Retrieves and parses webpage text with URL security policy checks and size caps.
"""

from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool
from src.web.retrieval.fetcher import WebFetcher

logger = get_logger()


class FetchWebpageTool(BaseTool):
    """Tool to retrieve and parse content from a webpage URL."""

    def __init__(self, config: Config | None = None, fetcher: WebFetcher | None = None):
        self.config = config or Config()
        self.fetcher = fetcher or WebFetcher(config=self.config)

    @property
    def name(self) -> str:
        return "fetch_webpage"

    @property
    def description(self) -> str:
        return "Fetches and extracts clean text content from a target webpage URL."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "url" in parameters and isinstance(parameters["url"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        url_str = str(parameters["url"]).strip()

        try:
            doc = self.fetcher.fetch_url(url_str)
            msg = f"Retrieved content from '{doc.domain}' ({len(doc.clean_text)} characters)."
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=msg,
                data={
                    "title": doc.title,
                    "url": doc.url,
                    "domain": doc.domain,
                    "content": doc.clean_text,
                    "headings": doc.headings,
                },
            )
        except Exception as e:
            logger.error(f"FetchWebpageTool failed for '{url_str}': {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to fetch webpage: {e}",
                error=str(e),
            )
