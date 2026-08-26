"""
ASTRA Security Permission Manager.
Evaluates permission requirements for tool requests.
"""

from src.brain.models import PermissionLevel, ToolRequest
from src.core.config import Config
from src.core.logger import get_logger

logger = get_logger()


class PermissionManager:
    """Evaluates security permissions for requested tools."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.mode = self.config.permissions_mode

    def is_permitted(self, request: ToolRequest, tool_permission_level: PermissionLevel) -> bool:
        """Check if request is authorized under current policy."""
        logger.info(
            f"PERMISSION_CHECK: tool='{request.tool_name}', level={tool_permission_level}, mode={self.mode}"
        )

        if tool_permission_level == PermissionLevel.SAFE:
            return True

        if tool_permission_level == PermissionLevel.CONFIRM:
            # Requires interactive confirmation in normal/strict mode
            return True  # Managed via ConfirmationHandler in executor

        if tool_permission_level == PermissionLevel.RESTRICTED:
            # Blocked by default in Phase 1
            logger.warning(f"PERMISSION_CHECK: Denied RESTRICTED tool '{request.tool_name}'")
            return False

        return False
