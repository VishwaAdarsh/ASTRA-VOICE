"""
Open Website Tool.
Opens URLs and approved website shortcuts in the default web browser.
"""

import time
from typing import Any
import webbrowser
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()


class OpenWebsiteTool(BaseTool):
    """Tool to open web URLs in system browser."""

    name = "open_website"
    description = "Opens websites (YouTube, Google, GitHub, URLs) in default web browser."
    permission_level = PermissionLevel.SAFE

    parameters_schema = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Website shortcut (e.g. 'youtube', 'google', 'github', 'reddit') or complete web URL to open",
            }
        },
        "required": ["target"],
    }


    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def validate(self, parameters: dict[str, Any]) -> bool:
        target = parameters.get("target")
        if not target or not isinstance(target, str):
            return False
        resolved = self.config.resolve_url(target)
        return resolved is not None

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        target = parameters.get("target", "").strip()

        url = self.config.resolve_url(target)
        if not url:
            return ToolResult(
                status=ExecutionStatus.INVALID_REQUEST,
                message=f"Invalid URL or website target '{target}'.",
                error=f"Cannot resolve target: {target}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            webbrowser.open(url)
            logger.info(f"Opened website URL '{url}' (target='{target}')")

            display_name = target.capitalize() if target in self.config.website_allowlist else target
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"{display_name} opened.",
                data={"target": target, "url": url},
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            logger.error(f"Failed to open website '{url}': {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to open website '{target}'.",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
