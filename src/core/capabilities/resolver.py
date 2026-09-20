"""
ASTRA Capability Resolver.
Resolves capability IDs to approved executable tool handlers with platform, state, and availability checks.
"""

import platform as sys_platform
from typing import Any, Optional

from src.core.capabilities.errors import (
    CapabilityDisabledError,
    CapabilityNotFoundError,
    CapabilityResolutionError,
    CapabilityUnavailableError,
    CapabilityUnsupportedPlatformError,
)
from src.core.capabilities.models import CapabilityDefinition, CapabilityState
from src.core.capabilities.registry import CapabilityRegistry
from src.core.logger import get_logger

logger = get_logger()


class CapabilityResolver:
    """
    Resolves capability requests to approved, executable tool implementations.
    Guarantees that unapproved, disabled, or platform-incompatible capabilities
    cannot execute.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        current_platform: Optional[str] = None,
    ):
        self.registry = registry
        self.current_platform = (current_platform or sys_platform.system()).lower()

    def resolve(
        self,
        capability_id_or_name: str,
        current_platform: Optional[str] = None,
    ) -> tuple[CapabilityDefinition, Any]:
        """
        Resolve a capability ID or tool name to its approved handler.
        
        Performs 5-step safety verification:
        1. Existence check in CapabilityRegistry
        2. Platform compatibility check
        3. Enabled state check
        4. Operational availability check
        5. Handler verification
        
        Returns:
            Tuple of (CapabilityDefinition, executable_handler)
            
        Raises:
            CapabilityNotFoundError: If capability does not exist.
            CapabilityUnsupportedPlatformError: If platform is incompatible.
            CapabilityDisabledError: If capability is explicitly disabled.
            CapabilityUnavailableError: If capability is degraded or unavailable.
            CapabilityResolutionError: If no executable handler is associated.
        """
        target_platform = (current_platform or self.current_platform).lower()

        # 1. Existence check
        try:
            capability = self.registry.get(capability_id_or_name)
        except CapabilityNotFoundError:
            logger.warning(f"RESOLVER: Unknown capability '{capability_id_or_name}'")
            raise CapabilityNotFoundError(capability_id_or_name)

        cap_id = capability.capability_id

        # 2. Platform compatibility check
        if not capability.is_available_on_platform(target_platform):
            logger.warning(
                f"RESOLVER: Capability '{cap_id}' unsupported on platform '{target_platform}'"
            )
            raise CapabilityUnsupportedPlatformError(
                cap_id,
                target_platform,
                capability.platforms,
            )

        # 3. Enabled state check
        if capability.state == CapabilityState.DISABLED:
            logger.warning(f"RESOLVER: Capability '{cap_id}' is disabled.")
            raise CapabilityDisabledError(cap_id)

        # 4. Operational availability check
        if capability.state == CapabilityState.UNAVAILABLE:
            logger.warning(f"RESOLVER: Capability '{cap_id}' is currently unavailable.")
            raise CapabilityUnavailableError(cap_id)

        # 5. Handler check
        if capability.handler is None:
            logger.error(f"RESOLVER: No executable handler bound to capability '{cap_id}'")
            raise CapabilityResolutionError(cap_id, "No executable tool handler is bound to this capability.")

        logger.debug(f"RESOLVER: Successfully resolved '{capability_id_or_name}' -> '{cap_id}'")
        return capability, capability.handler
