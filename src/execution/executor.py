"""
Tool Executor Engine.
Executes tool requests through registry validation, permission checks, pre/post verification, and error handling.
"""

import time
from src.brain.models import ExecutionStatus, PermissionLevel, ToolRequest, ToolResult
from src.core.exceptions import ToolNotFoundError
from src.core.logger import get_logger
from src.execution.verifier import ToolVerifier
from src.security.confirmation import ConfirmationHandler, ConsoleConfirmationHandler
from src.security.permissions import PermissionManager
from src.tools.registry import ToolRegistry

logger = get_logger()


from typing import Any, Optional
from src.brain.models import ExecutionStatus, PermissionLevel, ToolRequest, ToolResult
from src.core.capabilities.errors import (
    CapabilityDisabledError,
    CapabilityNotFoundError,
    CapabilityResolutionError,
    CapabilityUnavailableError,
    CapabilityUnsupportedPlatformError,
)
from src.core.capabilities.models import CapabilityDefinition, RiskLevel
from src.core.capabilities.resolver import CapabilityResolver
from src.core.capabilities.validation import SchemaValidator
from src.core.exceptions import ToolNotFoundError
from src.core.logger import get_logger
from src.execution.verifier import ToolVerifier
from src.security.confirmation import ConfirmationHandler, ConsoleConfirmationHandler
from src.security.permissions import PermissionManager
from src.tools.registry import ToolRegistry

logger = get_logger()


class ToolExecutor:
    """Orchestrates tool execution safety pipeline with Capability Registry resolution."""

    def __init__(
        self,
        registry: ToolRegistry,
        permission_manager: PermissionManager | None = None,
        verifier: ToolVerifier | None = None,
        confirmation_handler: ConfirmationHandler | None = None,
        resolver: CapabilityResolver | None = None,
        event_bus: Optional[Any] = None,
    ):
        self.registry = registry
        self.permission_manager = permission_manager or PermissionManager()
        self.verifier = verifier or ToolVerifier()
        self.confirmation_handler = confirmation_handler or ConsoleConfirmationHandler()
        self.event_bus = event_bus

        # Initialize or link CapabilityResolver
        if resolver:
            self.resolver = resolver
        elif hasattr(registry, "capability_registry"):
            self.resolver = CapabilityResolver(registry=registry.capability_registry)
        else:
            self.resolver = None

    def execute(
        self,
        request_or_name: ToolRequest | str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        """Process and execute a ToolRequest or (tool_name, parameters) through Capability resolution and safety checks."""
        if isinstance(request_or_name, str):
            request = ToolRequest(tool_name=request_or_name, parameters=parameters or {})
        else:
            request = request_or_name

        start_time = time.time()
        logger.info(f"EXECUTOR: Received request for tool/capability '{request.tool_name}'")

        cap_def: Optional[CapabilityDefinition] = None
        tool: Any = None

        # 1. Resolve Capability & Tool Handler
        if self.resolver:
            try:
                cap_def, tool = self.resolver.resolve(request.tool_name)
            except CapabilityNotFoundError as e:
                logger.warning(f"EXECUTOR: Capability '{request.tool_name}' not found: {e}")
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"I couldn't find the capability '{request.tool_name}'.",
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            except CapabilityUnsupportedPlatformError as e:
                logger.warning(f"EXECUTOR: Unsupported platform for '{request.tool_name}': {e}")
                return ToolResult(
                    status=ExecutionStatus.FAILED,
                    message=f"Capability '{request.tool_name}' is not supported on this platform.",
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            except (CapabilityDisabledError, CapabilityUnavailableError) as e:
                logger.warning(f"EXECUTOR: Capability '{request.tool_name}' unavailable/disabled: {e}")
                return ToolResult(
                    status=ExecutionStatus.FAILED,
                    message=f"Capability '{request.tool_name}' is currently unavailable.",
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
            except CapabilityResolutionError as e:
                logger.error(f"EXECUTOR: Resolution error for '{request.tool_name}': {e}")
                return ToolResult(
                    status=ExecutionStatus.FAILED,
                    message=f"I couldn't complete that action.",
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )
        else:
            # Fallback legacy registry lookup
            try:
                tool = self.registry.get(request.tool_name)
            except ToolNotFoundError as e:
                logger.warning(f"EXECUTOR: Tool '{request.tool_name}' not found in registry.")
                return ToolResult(
                    status=ExecutionStatus.NOT_FOUND,
                    message=f"I couldn't find the tool '{request.tool_name}'.",
                    error=str(e),
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        tool_name = getattr(tool, "name", request.tool_name)

        # 2. Schema Parameter Validation
        if cap_def and cap_def.input_schema:
            is_valid_schema, schema_errors = SchemaValidator.validate(
                request.parameters,
                cap_def.input_schema,
                capability_id=cap_def.capability_id,
            )
            if not is_valid_schema:
                err_msg = f"Invalid parameters for '{tool_name}': {'; '.join(schema_errors)}"
                logger.warning(f"EXECUTOR: Schema validation failed: {err_msg}")
                if self.event_bus:
                    try:
                        from src.core.events.models import ASTRAEvent, AstraEventType
                        self.event_bus.publish(
                            ASTRAEvent(
                                event_type=getattr(AstraEventType, "CAPABILITY_VALIDATION_FAILED", "CAPABILITY_VALIDATION_FAILED"),
                                source="executor",
                                payload={"capability_id": cap_def.capability_id, "errors": schema_errors},
                            )
                        )
                        self.event_bus.publish(
                            ASTRAEvent(
                                event_type=AstraEventType.CAPABILITY_EXECUTION_FAILED,
                                source="executor",
                                payload={"capability_id": cap_def.capability_id, "error": err_msg},
                            )
                        )
                    except Exception:
                        pass
                return ToolResult(
                    status=ExecutionStatus.INVALID_REQUEST,
                    message=err_msg,
                    error="Parameter validation failed",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        # 3. Tool-specific pre-execution verification
        is_valid, error_msg = self.verifier.verify_pre_execution(tool_name, request.parameters)
        if not is_valid:
            logger.warning(f"EXECUTOR: Pre-verification failed for '{tool_name}': {error_msg}")
            return ToolResult(
                status=ExecutionStatus.FAILED,
                message=error_msg or "Pre-execution check failed.",
                error=error_msg,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 4. Permission Check
        perm_level = getattr(tool, "permission_level", PermissionLevel.SAFE)
        if cap_def and cap_def.risk_level == RiskLevel.RISK_5:
            perm_level = PermissionLevel.RESTRICTED

        if not self.permission_manager.is_permitted(request, perm_level):
            logger.warning(f"EXECUTOR: Permission denied for tool '{tool_name}'")
            return ToolResult(
                status=ExecutionStatus.DENIED,
                message=f"Action '{tool_name}' is blocked by security policy.",
                error="Permission denied",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 5. User Confirmation check if required
        requires_conf = (
            (cap_def.requires_confirmation if cap_def else False)
            or perm_level == PermissionLevel.CONFIRM
        )
        if requires_conf:
            prompt_name = cap_def.name if cap_def else tool_name
            approved = self.confirmation_handler.confirm(
                f"Execute capability '{prompt_name}' with params {request.parameters}"
            )
            if not approved:
                logger.info(f"EXECUTOR: Action '{tool_name}' canceled by user.")
                return ToolResult(
                    status=ExecutionStatus.DENIED,
                    message=f"Execution of '{tool_name}' was canceled by user.",
                    error="User denied confirmation",
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

        # 6. Legacy Tool Validation
        if hasattr(tool, "validate") and not tool.validate(request.parameters):
            logger.warning(f"EXECUTOR: Tool '{tool_name}' validate() returned False for parameters {request.parameters}")
            return ToolResult(
                status=ExecutionStatus.INVALID_REQUEST,
                message=f"Invalid parameters for '{tool_name}'.",
                error="Parameter validation failed",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 7. Execute Tool Handler
        cap_id_str = cap_def.capability_id if cap_def else tool_name
        if self.event_bus:
            try:
                from src.core.events.models import ASTRAEvent, AstraEventType
                self.event_bus.publish(
                    ASTRAEvent(
                        event_type=AstraEventType.CAPABILITY_EXECUTION_STARTED,
                        source="executor",
                        payload={"capability_id": cap_id_str, "tool_name": tool_name, "parameters": request.parameters},
                    )
                )
            except Exception:
                pass

        try:
            logger.info(f"TOOL_EXECUTION: Executing '{tool_name}'")
            result = tool.execute(request.parameters)
            result.execution_time_ms = (time.time() - start_time) * 1000
        except Exception as e:
            logger.error(f"EXECUTOR: Exception thrown during execution of '{tool_name}': {e}", exc_info=True)
            result = ToolResult(
                status=ExecutionStatus.FAILED,
                message="I couldn't complete that action.",
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # 8. Post-execution Verification
        verified_result = self.verifier.verify_post_execution(
            result, tool_name=tool_name, parameters=request.parameters
        )

        if self.event_bus:
            try:
                from src.core.events.models import ASTRAEvent, AstraEventType
                if verified_result.status == ExecutionStatus.SUCCESS:
                    self.event_bus.publish(
                        ASTRAEvent(
                            event_type=AstraEventType.CAPABILITY_EXECUTION_COMPLETED,
                            source="executor",
                            payload={"capability_id": cap_id_str, "tool_name": tool_name},
                        )
                    )
                else:
                    self.event_bus.publish(
                        ASTRAEvent(
                            event_type=AstraEventType.CAPABILITY_EXECUTION_FAILED,
                            source="executor",
                            payload={"capability_id": cap_id_str, "tool_name": tool_name, "error": verified_result.error},
                        )
                    )
            except Exception:
                pass

        return verified_result

