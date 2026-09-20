"""
ASTRA Central Capability Registry.
Provides thread-safe registration, discovery, state management, and health synchronization for all ASTRA capabilities.
"""

import platform as sys_platform
import threading
from typing import Any, Optional

from src.core.capabilities.errors import (
    CapabilityNotFoundError,
    DuplicateCapabilityError,
)
from src.core.capabilities.models import (
    CapabilityCategory,
    CapabilityDefinition,
    CapabilityState,
)
from src.core.logger import get_logger

logger = get_logger()


class CapabilityRegistry:
    """
    Authoritative Central Registry for all declared ASTRA capabilities.
    Maintains capabilities, enforces uniqueness, manages lifecycle states,
    and synchronizes with subsystem health.
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self._lock = threading.RLock()
        self._capabilities: dict[str, CapabilityDefinition] = {}
        self._alias_map: dict[str, str] = {}  # short_name -> capability_id
        self.event_bus = event_bus

    def register(self, capability: CapabilityDefinition) -> None:
        """
        Register a new capability definition.
        Fails safely with DuplicateCapabilityError if ID is already registered.
        """
        if not isinstance(capability, CapabilityDefinition):
            raise TypeError(f"Expected CapabilityDefinition, got {type(capability).__name__}")

        cap_id = capability.capability_id.strip().lower()

        with self._lock:
            if cap_id in self._capabilities:
                raise DuplicateCapabilityError(cap_id)

            self._capabilities[cap_id] = capability

            # Map short name / trailing part (e.g. 'open_application' from 'system.open_application')
            short_name = cap_id.split(".")[-1]
            if short_name not in self._alias_map:
                self._alias_map[short_name] = cap_id

            logger.info(f"Capability '{cap_id}' (v{capability.version}) registered successfully.")

        # Publish event if event bus is available
        if self.event_bus:
            try:
                from src.core.events.models import ASTRAEvent, AstraEventType
                evt_type = getattr(AstraEventType, "CAPABILITY_REGISTERED", "CAPABILITY_REGISTERED")
                self.event_bus.publish(
                    ASTRAEvent(
                        event_type=evt_type,
                        source="capability_registry",
                        payload={"capability_id": cap_id, "category": capability.category.value},
                    )
                )
            except Exception as e:
                logger.warning(f"Error publishing CAPABILITY_REGISTERED event: {e}")

    def unregister(self, capability_id_or_alias: str) -> bool:
        """Remove a capability from the registry. Returns True if removed."""
        query = capability_id_or_alias.strip().lower()
        with self._lock:
            target_id = self._alias_map.get(query, query)
            if target_id in self._capabilities:
                del self._capabilities[target_id]
                # Clean up alias map
                to_delete = [k for k, v in self._alias_map.items() if v == target_id]
                for k in to_delete:
                    del self._alias_map[k]
                logger.info(f"Capability '{target_id}' unregistered.")
                return True
            return False

    def get(self, capability_id_or_alias: str) -> CapabilityDefinition:
        """Retrieve a capability definition by full ID or short alias."""
        query = capability_id_or_alias.strip().lower()
        with self._lock:
            target_id = self._alias_map.get(query, query)
            if target_id not in self._capabilities:
                raise CapabilityNotFoundError(query)
            return self._capabilities[target_id]

    def exists(self, capability_id_or_alias: str) -> bool:
        """Check if a capability exists by full ID or short alias."""
        query = capability_id_or_alias.strip().lower()
        with self._lock:
            return query in self._capabilities or query in self._alias_map

    def list(
        self,
        category: Optional[CapabilityCategory] = None,
        state: Optional[CapabilityState] = None,
        platform: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> list[CapabilityDefinition]:
        """List registered capabilities with optional filtering."""
        with self._lock:
            results = list(self._capabilities.values())

        if category is not None:
            results = [c for c in results if c.category == category]

        if state is not None:
            results = [c for c in results if c.state == state]

        if platform is not None:
            results = [c for c in results if c.is_available_on_platform(platform)]

        if tag is not None:
            results = [c for c in results if tag in c.tags]

        return sorted(results, key=lambda c: c.capability_id)

    def list_all(
        self,
        category: Optional[CapabilityCategory] = None,
        state: Optional[CapabilityState] = None,
        platform: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> list[CapabilityDefinition]:
        """Alias for list(). List registered capabilities with optional filtering."""
        return self.list(category=category, state=state, platform=platform, tag=tag)

    def list_by_category(self, category: CapabilityCategory) -> list[CapabilityDefinition]:
        """Filter capabilities by category."""
        return self.list(category=category)

    def list_by_state(self, state: CapabilityState) -> list[CapabilityDefinition]:
        """Filter capabilities by state."""
        return self.list(state=state)

    def list_by_platform(self, platform: str) -> list[CapabilityDefinition]:
        """Filter capabilities by platform."""
        return self.list(platform=platform)

    def find(self, query: str) -> list[CapabilityDefinition]:
        """Search capabilities by ID, name, description, or tags."""
        q = query.strip().lower()
        with self._lock:
            matches = [
                c for c in self._capabilities.values()
                if q in c.capability_id
                or q in c.name.lower()
                or q in c.description.lower()
                or any(q in t.lower() for t in c.tags)
            ]
        return sorted(matches, key=lambda c: c.capability_id)

    def enable(self, capability_id_or_alias: str) -> None:
        """Enable a capability."""
        self.set_state(capability_id_or_alias, CapabilityState.ENABLED)

    def disable(self, capability_id_or_alias: str) -> None:
        """Disable a capability."""
        self.set_state(capability_id_or_alias, CapabilityState.DISABLED)

    def set_state(
        self,
        capability_id_or_alias: str,
        state: CapabilityState,
        reason: str = "",
    ) -> None:
        """Update operational state of a capability."""
        cap = self.get(capability_id_or_alias)
        old_state = cap.state
        cap.state = state

        logger.info(f"Capability '{cap.capability_id}' state: {old_state.value} -> {state.value} ({reason})")

        if self.event_bus:
            try:
                from src.core.events.models import ASTRAEvent, AstraEventType
                self.event_bus.publish(
                    ASTRAEvent(
                        event_type=AstraEventType.CAPABILITY_AVAILABILITY_CHANGED if hasattr(AstraEventType, "CAPABILITY_AVAILABILITY_CHANGED") else "CAPABILITY_AVAILABILITY_CHANGED",
                        source="capability_registry",
                        payload={
                            "capability_id": cap.capability_id,
                            "old_state": old_state.value,
                            "new_state": state.value,
                            "reason": reason,
                        },
                    )
                )
            except Exception as e:
                logger.warning(f"Error publishing state change event: {e}")

    def is_available(
        self,
        capability_id_or_alias: str,
        current_platform: Optional[str] = None,
    ) -> bool:
        """Check if a capability is registered, executable, and supported on current platform."""
        try:
            cap = self.get(capability_id_or_alias)
        except CapabilityNotFoundError:
            return False

        target_platform = (current_platform or sys_platform.system()).lower()
        return cap.is_executable() and cap.is_available_on_platform(target_platform)

    def sync_with_health_manager(self, health_manager: Any) -> None:
        """
        Synchronize capability states with subsystem health diagnostics from HealthManager.
        Maps subsystem status (e.g. 'Web' degraded) to dependent capabilities.
        """
        if not health_manager or not hasattr(health_manager, "get_all_health"):
            return

        with self._lock:
            health_dict = health_manager.get_all_health()
            for cap in self._capabilities.values():
                for dep in cap.dependencies:
                    dep_upper = dep.upper()
                    if dep_upper in health_dict:
                        sub_health = health_dict[dep_upper]
                        status_str = getattr(sub_health.status, "value", str(sub_health.status))
                        if status_str in ("UNAVAILABLE", "DISABLED", "UNKNOWN"):
                            cap.state = CapabilityState.UNAVAILABLE
                        elif status_str == "DEGRADED" and cap.state not in (CapabilityState.DISABLED, CapabilityState.UNAVAILABLE):
                            cap.state = CapabilityState.DEGRADED
                        elif status_str in ("HEALTHY", "READY") and cap.state in (CapabilityState.UNAVAILABLE, CapabilityState.DEGRADED):
                            cap.state = CapabilityState.ENABLED

    def get_metrics(self) -> dict[str, Any]:
        """Return operational statistics of the Capability Registry."""
        with self._lock:
            total = len(self._capabilities)
            by_state = {s.value: 0 for s in CapabilityState}
            for c in self._capabilities.values():
                by_state[c.state.value] += 1

            return {
                "total_capabilities": total,
                "by_state": by_state,
                "registered_ids": sorted(list(self._capabilities.keys())),
            }
