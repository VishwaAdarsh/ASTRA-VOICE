"""
Project Registry and Open Project Tool.
Discovers user projects in configured project directories and opens them in editor/explorer.
"""

import os

import subprocess
from pathlib import Path
from typing import Any
from src.brain.models import ExecutionStatus, PermissionLevel, ToolResult
from src.core.config import Config
from src.core.logger import get_logger
from src.tools.base import BaseTool

logger = get_logger()


class ProjectRegistry:
    """Discovers project roots in configured project directories."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def find_project(self, project_name: str) -> Path | None:
        """Search project directories for a matching project folder."""
        query = project_name.lower().strip()
        for base_dir in self.config.project_dirs:
            if not base_dir.exists():
                continue
            for item in base_dir.iterdir():
                if item.is_dir():
                    if query in item.name.lower():
                        return item
        return None


class OpenProjectTool(BaseTool):
    """Tool to open a project folder in editor or file explorer."""

    def __init__(self, config: Config | None = None, project_registry: ProjectRegistry | None = None):
        self.config = config or Config()
        self.project_registry = project_registry or ProjectRegistry(config=self.config)

    @property
    def name(self) -> str:
        return "open_project"

    @property
    def description(self) -> str:
        return "Discovers and opens a software project folder in configured project directories."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.SAFE

    def validate(self, parameters: dict[str, Any]) -> bool:
        return "project_name" in parameters and isinstance(parameters["project_name"], str)

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        project_name = str(parameters["project_name"]).strip()
        project_path = self.project_registry.find_project(project_name)

        if not project_path or not project_path.exists():
            return ToolResult(
                status=ExecutionStatus.NOT_FOUND,
                message=f"Project '{project_name}' not found in project directories.",
            )

        try:
            logger.info(f"Opening project '{project_path.name}' at '{project_path}'")
            if hasattr(os, "startfile"):
                os.startfile(str(project_path))
            else:
                subprocess.Popen(["cmd.exe", "/c", "start", "", str(project_path)])

            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Opened project '{project_path.name}'.",
                data={"project_name": project_path.name, "path": str(project_path)},
            )
        except Exception as e:
            logger.error(f"OpenProjectTool failed: {e}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=f"Failed to open project: {e}",
                error=str(e),
            )
