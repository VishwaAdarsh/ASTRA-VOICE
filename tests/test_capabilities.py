import threading
import time
import pytest
from typing import Any

from src.brain.models import ExecutionStatus, ToolResult
from src.core.capabilities.errors import (
    CapabilityDisabledError,
    CapabilityNotFoundError,
    CapabilityResolutionError,
    CapabilityUnavailableError,
    CapabilityUnsupportedPlatformError,
    CapabilityValidationError,
    DuplicateCapabilityError,
)
from src.core.capabilities.models import (
    CapabilityCategory,
    CapabilityDefinition,
    CapabilityState,
    RiskLevel,
)
from src.core.capabilities.registry import CapabilityRegistry
from src.core.capabilities.resolver import CapabilityResolver
from src.core.capabilities.schemas import LLMToolSchemaAdapter
from src.core.capabilities.validation import SchemaValidator
from src.core.events.bus import EventBus
from src.core.events.models import AstraEventType
from src.core.health import HealthManager, HealthStatus
from src.execution.executor import ToolExecutor
from src.security.confirmation import AutoApproveConfirmationHandler, ConfirmationHandler
from src.security.permissions import PermissionLevel, PermissionManager
from src.tools.base import BaseTool
from src.tools.registry import ToolRegistry


class DummyTool(BaseTool):
    name: str = "dummy_action"
    description: str = "A dummy action tool for testing"
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "target": {"type": "string"},
            "count": {"type": "integer"},
            "mode": {"type": "string", "enum": ["fast", "slow"]},
        },
        "required": ["target"],
    }

    def validate(self, parameters: dict[str, Any]) -> bool:
        return True

    def execute(self, parameters: dict[str, Any]) -> ToolResult:
        return ToolResult(
            status=ExecutionStatus.SUCCESS,
            message="Success",
            data={"result": parameters},
        )


# ---------------------------------------------------------------------------
# 1. Capability Model & ID Validation
# ---------------------------------------------------------------------------

def test_capability_definition_valid():
    cap = CapabilityDefinition(
        capability_id="system.restart_service",
        name="Restart Service",
        description="Restarts a system service",
        category=CapabilityCategory.SYSTEM,
        risk_level=RiskLevel.RISK_3,
        platforms=["windows", "linux"],
    )
    assert cap.capability_id == "system.restart_service"
    assert cap.category == CapabilityCategory.SYSTEM
    assert cap.is_available_on_platform("windows") is True
    assert cap.is_available_on_platform("darwin") is False
    assert cap.is_executable() is True


def test_capability_definition_invalid_id():
    with pytest.raises(ValueError, match="Invalid capability ID format"):
        CapabilityDefinition(
            capability_id="invalid_id_without_dot",
            name="Invalid",
            description="Invalid ID format",
            category=CapabilityCategory.SYSTEM,
        )


# ---------------------------------------------------------------------------
# 2. Capability Registry: Registration, Duplicates, Filtering
# ---------------------------------------------------------------------------

def test_registry_registration_and_get():
    registry = CapabilityRegistry()
    cap = CapabilityDefinition(
        capability_id="filesystem.read_file",
        name="Read File",
        description="Reads file contents",
        category=CapabilityCategory.FILESYSTEM,
        risk_level=RiskLevel.RISK_1,
        read_only=True,
    )
    registry.register(cap)

    assert registry.exists("filesystem.read_file") is True
    retrieved = registry.get("filesystem.read_file")
    assert retrieved.capability_id == "filesystem.read_file"
    assert retrieved.read_only is True


def test_registry_rejects_duplicate_ids():
    registry = CapabilityRegistry()
    cap1 = CapabilityDefinition(
        capability_id="web.fetch",
        name="Fetch Webpage",
        description="Fetch",
        category=CapabilityCategory.WEB,
    )
    cap2 = CapabilityDefinition(
        capability_id="web.fetch",
        name="Fetch Duplicate",
        description="Duplicate",
        category=CapabilityCategory.WEB,
    )
    registry.register(cap1)
    with pytest.raises(DuplicateCapabilityError):
        registry.register(cap2)


def test_registry_filters():
    registry = CapabilityRegistry()
    cap_sys = CapabilityDefinition(
        capability_id="system.volume",
        name="Volume",
        description="Control volume",
        category=CapabilityCategory.SYSTEM,
        state=CapabilityState.ENABLED,
        platforms=["windows"],
    )
    cap_web = CapabilityDefinition(
        capability_id="web.search",
        name="Search",
        description="Web search",
        category=CapabilityCategory.WEB,
        state=CapabilityState.DISABLED,
        platforms=["windows", "linux", "darwin"],
    )
    registry.register(cap_sys)
    registry.register(cap_web)

    # Filter by category
    sys_caps = registry.list_by_category(CapabilityCategory.SYSTEM)
    assert len(sys_caps) == 1
    assert sys_caps[0].capability_id == "system.volume"

    # Filter by state
    enabled_caps = registry.list_by_state(CapabilityState.ENABLED)
    assert len(enabled_caps) == 1
    assert enabled_caps[0].capability_id == "system.volume"

    # Filter by platform
    darwin_caps = registry.list_by_platform("darwin")
    assert len(darwin_caps) == 1
    assert darwin_caps[0].capability_id == "web.search"


# ---------------------------------------------------------------------------
# 3. Schema Validation
# ---------------------------------------------------------------------------

def test_schema_validator_valid():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer"},
            "active": {"type": "boolean"},
        },
        "required": ["name"],
    }
    # Should not raise
    SchemaValidator.validate({"name": "test", "count": 5, "active": True}, schema)


def test_schema_validator_missing_required():
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    with pytest.raises(CapabilityValidationError, match="Missing required parameter: 'name'"):
        SchemaValidator.validate({}, schema, raise_on_error=True)


def test_schema_validator_type_mismatch():
    schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}},
    }
    with pytest.raises(CapabilityValidationError, match="expected type 'integer'"):
        SchemaValidator.validate({"count": "not_an_integer"}, schema, raise_on_error=True)


def test_schema_validator_enum_mismatch():
    schema = {
        "type": "object",
        "properties": {"mode": {"type": "string", "enum": ["fast", "slow"]}},
    }
    with pytest.raises(CapabilityValidationError, match="is not one of allowed values"):
        SchemaValidator.validate({"mode": "medium"}, schema, raise_on_error=True)


# ---------------------------------------------------------------------------
# 4. Capability Resolver
# ---------------------------------------------------------------------------

def test_resolver_successful_resolution():
    registry = CapabilityRegistry()
    cap = CapabilityDefinition(
        capability_id="system.dummy_action",
        name="Dummy",
        description="Dummy action",
        category=CapabilityCategory.SYSTEM,
        platforms=["windows", "linux", "darwin"],
        state=CapabilityState.ENABLED,
        handler=lambda **kw: "ok",
    )
    registry.register(cap)
    resolver = CapabilityResolver(registry)

    resolved, handler = resolver.resolve("system.dummy_action")
    assert resolved.capability_id == "system.dummy_action"

    # Resolving via alias (short name)
    resolved_alias, handler2 = resolver.resolve("dummy_action")
    assert resolved_alias.capability_id == "system.dummy_action"


def test_resolver_not_found():
    registry = CapabilityRegistry()
    resolver = CapabilityResolver(registry)
    with pytest.raises(CapabilityNotFoundError):
        resolver.resolve("nonexistent.tool")


def test_resolver_unsupported_platform():
    registry = CapabilityRegistry()
    cap = CapabilityDefinition(
        capability_id="system.mac_only",
        name="Mac Only",
        description="Mac only tool",
        category=CapabilityCategory.SYSTEM,
        platforms=["darwin"],
        handler=lambda: None,
    )
    registry.register(cap)
    resolver = CapabilityResolver(registry)

    with pytest.raises(CapabilityUnsupportedPlatformError):
        resolver.resolve("system.mac_only", current_platform="windows")


def test_resolver_disabled():
    registry = CapabilityRegistry()
    cap = CapabilityDefinition(
        capability_id="system.disabled_tool",
        name="Disabled",
        description="Disabled tool",
        category=CapabilityCategory.SYSTEM,
        state=CapabilityState.DISABLED,
        platforms=["windows"],
        handler=lambda: None,
    )
    registry.register(cap)
    resolver = CapabilityResolver(registry)

    with pytest.raises(CapabilityDisabledError):
        resolver.resolve("system.disabled_tool", current_platform="windows")


def test_resolver_unavailable():
    registry = CapabilityRegistry()
    cap = CapabilityDefinition(
        capability_id="system.unavail_tool",
        name="Unavailable",
        description="Unavailable tool",
        category=CapabilityCategory.SYSTEM,
        state=CapabilityState.UNAVAILABLE,
        platforms=["windows"],
        handler=lambda: None,
    )
    registry.register(cap)
    resolver = CapabilityResolver(registry)

    with pytest.raises(CapabilityUnavailableError):
        resolver.resolve("system.unavail_tool", current_platform="windows")


def test_resolver_missing_handler():
    registry = CapabilityRegistry()
    cap = CapabilityDefinition(
        capability_id="system.no_handler",
        name="No Handler",
        description="No handler",
        category=CapabilityCategory.SYSTEM,
        state=CapabilityState.ENABLED,
        platforms=["windows"],
        handler=None,
    )
    registry.register(cap)
    resolver = CapabilityResolver(registry)

    with pytest.raises(CapabilityResolutionError, match="No executable tool handler is bound"):
        resolver.resolve("system.no_handler", current_platform="windows")


# ---------------------------------------------------------------------------
# 5. ToolRegistry Integration & Backward Compatibility
# ---------------------------------------------------------------------------

def test_tool_registry_auto_maps_to_capabilities():
    tool_reg = ToolRegistry()
    dummy = DummyTool()
    tool_reg.register(dummy)

    # Legacy access
    assert tool_reg.has_tool("dummy_action") is True
    assert tool_reg.get("dummy_action") == dummy

    # Capability Registry access
    cap_reg = tool_reg.capability_registry
    assert cap_reg.exists("other.dummy_action") is True
    cap = cap_reg.get("other.dummy_action")
    assert cap.name == "dummy_action"
    assert cap.handler == dummy


# ---------------------------------------------------------------------------
# 6. ToolExecutor with Capability Pipeline & Event Bus
# ---------------------------------------------------------------------------

def test_executor_with_capability_pipeline_success():
    event_bus = EventBus()
    events_received = []

    def on_event(event):
        events_received.append(event.event_type)

    event_bus.subscribe(AstraEventType.CAPABILITY_EXECUTION_STARTED, on_event)
    event_bus.subscribe(AstraEventType.CAPABILITY_EXECUTION_COMPLETED, on_event)

    tool_reg = ToolRegistry()
    dummy = DummyTool()
    tool_reg.register(dummy)

    executor = ToolExecutor(registry=tool_reg, event_bus=event_bus)
    result = executor.execute("dummy_action", {"target": "my_file.txt", "count": 3, "mode": "fast"})

    time.sleep(0.1)
    assert result.status.value == "SUCCESS"
    assert result.data["result"]["target"] == "my_file.txt"
    assert AstraEventType.CAPABILITY_EXECUTION_STARTED in events_received
    assert AstraEventType.CAPABILITY_EXECUTION_COMPLETED in events_received


def test_executor_parameter_validation_failure():
    event_bus = EventBus()
    events_received = []

    def on_event(event):
        events_received.append(event.event_type)

    event_bus.subscribe(AstraEventType.CAPABILITY_EXECUTION_FAILED, on_event)

    tool_reg = ToolRegistry()
    dummy = DummyTool()
    tool_reg.register(dummy)

    executor = ToolExecutor(registry=tool_reg, event_bus=event_bus)
    # Missing required 'target' parameter
    result = executor.execute("dummy_action", {"count": 3})

    time.sleep(0.1)
    assert result.status.value == "INVALID_REQUEST"
    assert "Missing required parameter" in (result.message or "")
    assert AstraEventType.CAPABILITY_EXECUTION_FAILED in events_received


def test_executor_permission_denied_risk5():
    tool_reg = ToolRegistry()
    dummy = DummyTool()
    tool_reg.register(dummy)

    # Set capability to RISK_5 (RESTRICTED)
    cap = tool_reg.capability_registry.get("other.dummy_action")
    cap.risk_level = RiskLevel.RISK_5

    perm_mgr = PermissionManager()

    executor = ToolExecutor(registry=tool_reg, permission_manager=perm_mgr)
    result = executor.execute("dummy_action", {"target": "test"})

    assert result.status.value == "DENIED"
    assert "Permission denied" in (result.error or "")


def test_executor_confirmation_rejected():
    tool_reg = ToolRegistry()
    dummy = DummyTool()
    tool_reg.register(dummy)

    # Require confirmation
    cap = tool_reg.capability_registry.get("other.dummy_action")
    cap.requires_confirmation = True

    # ConfirmationHandler that rejects
    conf_handler = AutoApproveConfirmationHandler(approve=False)

    executor = ToolExecutor(registry=tool_reg, confirmation_handler=conf_handler)
    result = executor.execute("dummy_action", {"target": "test"})

    assert result.status.value == "DENIED"
    assert "canceled by user" in (result.message or "")


# ---------------------------------------------------------------------------
# 7. Health Synchronization
# ---------------------------------------------------------------------------

def test_health_synchronization():
    cap_reg = CapabilityRegistry()
    cap = CapabilityDefinition(
        capability_id="vision.screen_reader",
        name="Screen Reader",
        description="Reads screen text",
        category=CapabilityCategory.VISION,
        dependencies=["OCR"],
        state=CapabilityState.ENABLED,
    )
    cap_reg.register(cap)

    # Create HealthManager and record OCR failure
    health_mgr = HealthManager()
    health_mgr.set_status(
        "OCR",
        HealthStatus.UNAVAILABLE,
        message="Tesseract OCR binary not found",
    )

    cap_reg.sync_with_health_manager(health_mgr)

    # Capability should now be UNAVAILABLE due to unhealthy dependency
    assert cap.state == CapabilityState.UNAVAILABLE


# ---------------------------------------------------------------------------
# 8. LLM Tool Schema Adapter
# ---------------------------------------------------------------------------

def test_llm_tool_schema_adapter():
    cap_reg = CapabilityRegistry()
    cap1 = CapabilityDefinition(
        capability_id="filesystem.create_file",
        name="create_file",
        description="Creates a new file",
        category=CapabilityCategory.FILESYSTEM,
        input_schema={"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]},
        platforms=["windows", "linux"],
        state=CapabilityState.ENABLED,
    )
    cap2 = CapabilityDefinition(
        capability_id="system.mac_only_setting",
        name="mac_setting",
        description="Mac setting",
        category=CapabilityCategory.SYSTEM,
        platforms=["darwin"],
        state=CapabilityState.ENABLED,
    )
    cap3 = CapabilityDefinition(
        capability_id="system.disabled_setting",
        name="disabled_setting",
        description="Disabled setting",
        category=CapabilityCategory.SYSTEM,
        platforms=["windows"],
        state=CapabilityState.DISABLED,
    )
    cap_reg.register(cap1)
    cap_reg.register(cap2)
    cap_reg.register(cap3)

    schemas = LLMToolSchemaAdapter.generate_schemas(
        cap_reg.list_all(),
        current_platform="windows",
        use_short_name=True,
    )

    # Only cap1 should be included (cap2 is darwin-only, cap3 is disabled)
    assert len(schemas) == 1
    assert schemas[0]["name"] == "create_file"
    assert schemas[0]["description"] == "Creates a new file"
    assert "filename" in schemas[0]["parameters"]["properties"]


# ---------------------------------------------------------------------------
# 9. Thread Safety
# ---------------------------------------------------------------------------

def test_registry_thread_safety():
    registry = CapabilityRegistry()
    num_threads = 10
    caps_per_thread = 20
    errors = []

    def worker(thread_idx: int):
        for i in range(caps_per_thread):
            cap_id = f"other.tool_{thread_idx}_{i}"
            try:
                cap = CapabilityDefinition(
                    capability_id=cap_id,
                    name=f"tool_{thread_idx}_{i}",
                    description="Thread safety test capability",
                    category=CapabilityCategory.OTHER,
                )
                registry.register(cap)
                _ = registry.get(cap_id)
                _ = registry.list_all()
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(registry.list_all()) == num_threads * caps_per_thread
