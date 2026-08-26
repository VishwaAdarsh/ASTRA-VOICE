"""
Unit tests for Permission System.
"""

from src.brain.models import PermissionLevel, ToolRequest
from src.core.config import Config
from src.security.permissions import PermissionManager


def test_permission_safe():
    config = Config()
    pm = PermissionManager(config=config)

    request = ToolRequest(tool_name="open_calculator")
    assert pm.is_permitted(request, PermissionLevel.SAFE) is True


def test_permission_restricted():
    config = Config()
    pm = PermissionManager(config=config)

    request = ToolRequest(tool_name="delete_system_files")
    assert pm.is_permitted(request, PermissionLevel.RESTRICTED) is False
