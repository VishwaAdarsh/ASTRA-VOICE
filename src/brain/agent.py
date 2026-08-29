"""
ASTRA Agent Orchestrator (Phase 4 Upgraded).
Coordinates LLM Reasoning, Context Management, Task Planning, Permission Enforcement, Tool Execution, and Deterministic Fallback.
"""

import time
from typing import Any

from src.brain.context.manager import ContextManager
from src.brain.intent import IntentRecognizer, RuleBasedIntentRecognizer
from src.brain.llm.client import LLMClient
from src.brain.llm.models import DecisionType, LLMDecision, ModelConfig

from src.brain.llm.provider import LLMProvider
from src.brain.models import Command, ExecutionStatus, IntentType, ToolRequest, ToolResult
from src.brain.planning.planner import TaskPlanner
from src.brain.planning.validator import PlanValidator
from src.brain.prompts.system import ASTRA_SYSTEM_PROMPT_V1
from src.brain.prompts.tool_selection import generate_tool_schemas
from src.brain.router import IntentRouter
from src.core.config import Config
from src.core.exceptions import AstraError
from src.core.logger import get_logger
from src.execution.executor import ToolExecutor
from src.execution.verifier import ToolVerifier
from src.security.permissions import PermissionManager
from src.tools.applications import ApplicationStatusTool, CloseApplicationTool, OpenProjectTool
from src.tools.applications import OpenApplicationTool
from src.tools.browser import OpenWebsiteTool
from src.tools.filesystem import (
    CopyFileTool,
    CreateFolderTool,
    CreateTextFileTool,
    DeleteFileTool,
    FileMetadataTool,
    MoveFileTool,
    OpenFileTool,
    OrganizeFolderTool,
    RenameFileTool,
    SearchFilesTool,
)
from src.automation.manager import AutomationManager
from src.automation.notification import NotificationManager
from src.core.health import HealthManager
from src.core.recovery import CrashRecoveryManager
from src.security.auditor import SecurityAuditor
from src.security.injection import PromptInjectionDefense
from src.tools.filesystem import OpenFolderTool
from src.tools.registry import ToolRegistry
from src.task.manager import TaskManager
from src.memory.manager import MemoryManager
from src.tools.memory import (
    ForgetMemoryTool,
    ListMemoriesTool,
    RememberTool,
    RetrieveMemoryTool,
)
from src.tools.system import (
    ResourceInformationTool,
    ScreenshotTool,
    SystemInformationTool,
    VolumeControlTool,
)
from src.tools.vision import (
    AnalyzeActiveWindowTool,
    AnalyzeImageTool,
    AnalyzeScreenTool,
    ReadScreenTextTool,
)
from src.tools.web import FetchWebpageTool, ResearchTopicTool, SearchWebTool
from src.vision.context.manager import VisionManager

logger = get_logger()





class AstraAgent:
    """Core ASTRA Agent Orchestrator for Phase 4 & Phase 5 Computer Control."""

    def __init__(
        self,
        config: Config | None = None,
        llm_provider: LLMProvider | None = None,
        intent_recognizer: IntentRecognizer | None = None,
        tool_registry: ToolRegistry | None = None,
        permission_manager: PermissionManager | None = None,
        context_manager: ContextManager | None = None,
        executor: ToolExecutor | None = None,
    ):
        self.config = config or Config()
        self.fallback_recognizer = intent_recognizer or RuleBasedIntentRecognizer()
        self.router = IntentRouter()
        self.registry = tool_registry or ToolRegistry()
        self.permission_manager = permission_manager or PermissionManager(config=self.config)
        self.verifier = ToolVerifier(config=self.config)

        # Initialize Subsystems (Phases 1-11)
        self.health_manager = HealthManager(config=self.config)
        self.security_auditor = SecurityAuditor(config=self.config)
        self.injection_defense = PromptInjectionDefense(config=self.config, auditor=self.security_auditor)
        self.context_manager = context_manager or ContextManager()
        self.memory_manager = MemoryManager(config=self.config)
        self.vision_manager = VisionManager(config=self.config)
        self.task_manager = TaskManager(config=self.config, registry=self.registry)
        self.automation_manager = AutomationManager(config=self.config, registry=self.registry, task_manager=self.task_manager)
        self.notification_manager = self.automation_manager.notification_manager
        self.crash_recovery_manager = CrashRecoveryManager(config=self.config, task_manager=self.task_manager, automation_manager=self.automation_manager)

        # Perform startup recovery audit
        self.crash_recovery_manager.perform_startup_recovery()

        self.planner = TaskPlanner()
        self.plan_validator = PlanValidator(registry=self.registry, permission_manager=self.permission_manager)
        self.executor = executor or ToolExecutor(
            registry=self.registry,
            permission_manager=self.permission_manager,
            verifier=self.verifier,
        )

        # Initialize Phase 4 LLM Subsystem
        model_config = ModelConfig(
            provider=self.config.llm_provider,
            model=self.config.llm_model,
            temperature=self.config.llm_temperature,
            max_output_tokens=self.config.llm_max_output_tokens,
            timeout=self.config.llm_timeout,
            retry_count=self.config.llm_retry_count,
            api_key=self.config.llm_api_key,
        )
        self.llm_client = LLMClient(config=model_config, provider=llm_provider)


        # Register standard allowlisted tools
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register built-in tool instances across Phase 1, 5, 6, 7 & 8."""
        # Phase 1 Core Tools
        self.registry.register(OpenApplicationTool(config=self.config))
        self.registry.register(OpenFolderTool(config=self.config))
        self.registry.register(OpenWebsiteTool(config=self.config))
        self.registry.register(SystemInformationTool())

        # Phase 5 Filesystem
        self.registry.register(SearchFilesTool(config=self.config))
        self.registry.register(FileMetadataTool(config=self.config))
        self.registry.register(OpenFileTool(config=self.config))
        self.registry.register(CreateFolderTool(config=self.config))
        self.registry.register(CreateTextFileTool(config=self.config))
        self.registry.register(RenameFileTool(config=self.config))
        self.registry.register(MoveFileTool(config=self.config))
        self.registry.register(CopyFileTool(config=self.config))
        self.registry.register(DeleteFileTool(config=self.config))
        self.registry.register(OrganizeFolderTool(config=self.config))

        # Phase 5 Applications
        self.registry.register(ApplicationStatusTool(config=self.config))
        self.registry.register(CloseApplicationTool(config=self.config))
        self.registry.register(OpenProjectTool(config=self.config))

        # Phase 5 System
        self.registry.register(ResourceInformationTool())
        self.registry.register(ScreenshotTool(config=self.config))
        self.registry.register(VolumeControlTool())

        # Phase 6 Web Intelligence
        self.registry.register(SearchWebTool(config=self.config))
        self.registry.register(FetchWebpageTool(config=self.config))
        self.registry.register(ResearchTopicTool(config=self.config))

        # Phase 7 Memory
        self.registry.register(RememberTool(config=self.config, memory_manager=self.memory_manager))
        self.registry.register(RetrieveMemoryTool(config=self.config, memory_manager=self.memory_manager))
        self.registry.register(ForgetMemoryTool(config=self.config, memory_manager=self.memory_manager))
        self.registry.register(ListMemoriesTool(config=self.config, memory_manager=self.memory_manager))

        # Phase 8 Vision
        self.registry.register(AnalyzeScreenTool(config=self.config, vision_manager=self.vision_manager))
        self.registry.register(AnalyzeActiveWindowTool(config=self.config, vision_manager=self.vision_manager))
        self.registry.register(AnalyzeImageTool(config=self.config, vision_manager=self.vision_manager))
        self.registry.register(ReadScreenTextTool(config=self.config, vision_manager=self.vision_manager))

        logger.info(f"Registered {len(self.registry.list_tools())} tools: {self.registry.list_tools()}")




    def process_command(self, raw_input: str) -> tuple[str, ToolResult]:
        """Process a user command through the Controlled Multi-Step Agent Orchestration Loop."""
        logger.info(f"AGENT_REQUEST_STARTED: '{raw_input}'")

        command = Command(
            raw_text=raw_input,
            normalized_text=raw_input.strip().lower(),
        )

        # Add user message to Context Manager
        self.context_manager.add_user_message(raw_input)

        max_iterations = getattr(self.config, "agent_max_iterations", 5)
        timeout_sec = getattr(self.config, "agent_timeout", 30.0)
        start_time = time.time()

        tool_schemas = generate_tool_schemas(self.registry)
        tool_history: list[dict[str, Any]] = []
        seen_tool_signatures: list[str] = []
        last_tool_result: ToolResult | None = None

        try:
            iteration = 0
            while iteration < max_iterations:
                # Check overall agent request timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_sec:
                    logger.warning(f"AGENT_TIMEOUT: Request exceeded {timeout_sec}s threshold.")
                    timeout_res = ToolResult(
                        status=ExecutionStatus.FAILED,
                        message="Request exceeded execution timeout limit.",
                        error="Execution timeout",
                    )
                    return "I couldn't complete the task within the allowed time limit.", timeout_res

                iteration += 1
                logger.info(f"AGENT_ITERATION: {iteration}/{max_iterations}")

                # Build context-aware prompt with prior step results
                formatted_context = self.context_manager.get_formatted_context_prompt()

                steps_summary_lines = []
                for idx, step_info in enumerate(tool_history):
                    steps_summary_lines.append(
                        f"Step {idx+1}: Tool '{step_info['tool']}' (args={step_info['args']}) -> "
                        f"Status: {step_info['status']}, Result: {step_info['message']}, Data: {step_info['data']}"
                    )
                steps_context = "\n".join(steps_summary_lines) if steps_summary_lines else "None (Initial Step)"

                full_prompt = (
                    f"Context History:\n{formatted_context}\n\n"
                    f"User Command:\n{raw_input}\n\n"
                    f"Execution Steps Taken So Far:\n{steps_context}\n\n"
                    f"Instructions: If the user request has been fully satisfied, return a natural conversational response. "
                    f"If another action is required to fulfill the request, select the next appropriate tool."
                )

                decision = self.llm_client.generate_decision(
                    prompt=full_prompt,
                    system_prompt=ASTRA_SYSTEM_PROMPT_V1,
                    tool_schemas=tool_schemas,
                )

                # Case 1: Final Conversational Response (Task Completed)
                if decision.decision_type == DecisionType.RESPONSE:
                    response_text = decision.message or "Task completed."
                    final_result = last_tool_result or ToolResult(status=ExecutionStatus.SUCCESS, message=response_text)
                    self.context_manager.record_turn_result(response_text)
                    logger.info(f"AGENT_COMPLETED: Final response generated in iteration {iteration}")
                    return response_text, final_result

                # Case 2: Clarification Request
                elif decision.decision_type == DecisionType.CLARIFICATION:
                    response_text = decision.message or "Could you please clarify your request?"
                    final_result = ToolResult(status=ExecutionStatus.SUCCESS, message=response_text)
                    self.context_manager.record_turn_result(response_text)
                    return response_text, final_result

                # Case 3: Structured Tool Call
                elif decision.decision_type == DecisionType.TOOL_CALL and decision.tool_name:
                    tool_name = decision.tool_name
                    arguments = decision.arguments or {}
                    logger.info(f"AGENT_TOOL_REQUEST: tool='{tool_name}', args={arguments}")

                    # Repetitive loop detection
                    call_sig = f"{tool_name}:{sorted(arguments.items())}"
                    if seen_tool_signatures.count(call_sig) >= 2:
                        logger.warning(f"LOOP_DETECTED: Tool '{call_sig}' repeated 2+ times. Halting loop.")
                        loop_res = ToolResult(
                            status=ExecutionStatus.FAILED,
                            message="Repetitive tool execution loop detected.",
                            error="Loop limit exceeded",
                        )
                        return f"I stopped because the action '{tool_name}' was repeating without progress.", loop_res

                    seen_tool_signatures.append(call_sig)

                    # Execute tool through authoritative security and verification pipeline
                    tool_request = ToolRequest(
                        tool_name=tool_name,
                        parameters=arguments,
                    )
                    tool_result = self.executor.execute(tool_request)
                    last_tool_result = tool_result

                    # Record step in local iteration history
                    tool_history.append({
                        "tool": tool_name,
                        "args": arguments,
                        "status": tool_result.status.value,
                        "message": tool_result.message,
                        "data": tool_result.data or {},
                        "verified": getattr(tool_result, "verified", True),
                    })

                    self.context_manager.record_turn_result(
                        self._format_response(tool_result),
                        tool_name,
                        tool_result.data,
                    )

                    # Single-step completion optimization for simple non-compound open/launch commands
                    is_simple_open = raw_input.lower().startswith(("open ", "launch ", "start "))
                    has_compound_intent = any(kw in raw_input.lower() for kw in (" and ", " then ", " after ", "find", "search", "look"))
                    if len(tool_history) == 1 and is_simple_open and not has_compound_intent:
                        response_text = self._format_response(tool_result)
                        return response_text, tool_result


                elif decision.decision_type == DecisionType.PLAN and decision.steps:
                    # Multi-step plan execution
                    logger.info("LLM_PLAN: Executing multi-step plan")
                    plan = self.planner.create_plan_from_decision(decision, raw_input)
                    is_valid, err = self.plan_validator.validate(plan)
                    if not is_valid:
                        logger.warning(f"Plan validation failed: {err}")
                        return self._fallback_execution(command)

                    last_result = None
                    for step in plan.steps:
                        req = ToolRequest(tool_name=step.tool_name, parameters=step.arguments)
                        last_result = self.executor.execute(req)
                        if last_result.status != ExecutionStatus.SUCCESS:
                            break

                    response_text = self._format_response(last_result) if last_result else "Plan completed."
                    return response_text, last_result or ToolResult(status=ExecutionStatus.SUCCESS, message="Plan executed.")

                else:
                    logger.info("LLM returned fallback/error decision. Invoking fallback engine.")
                    return self._fallback_execution(command)

            # Reached max iterations limit
            logger.warning(f"AGENT_MAX_ITERATIONS_REACHED: {max_iterations}")
            max_iter_res = ToolResult(
                status=ExecutionStatus.FAILED,
                message="I reached the maximum number of steps allowed for this task.",
                error="Max iterations limit reached",
            )
            return "I reached the maximum number of steps allowed for this task.", max_iter_res


        except Exception as e:
            logger.error(f"Error during agent orchestration: {e}. Switching to fallback engine.", exc_info=True)
            return self._fallback_execution(command)


    def _fallback_execution(self, command: Command) -> tuple[str, ToolResult]:
        """Deterministic Rule-Based Fallback Engine."""
        logger.info(f"FALLBACK_ENGINE: Processing command '{command.raw_text}'")
        intent = self.fallback_recognizer.recognize(command)

        if intent.intent_type == IntentType.CONVERSATION:
            resp = "Hello! I am ASTRA, your desktop personal AI assistant. How can I help you today?"
            result = ToolResult(status=ExecutionStatus.SUCCESS, message=resp)
            self.context_manager.record_turn_result(resp)
            return resp, result

        if intent.intent_type == IntentType.STOP:
            if hasattr(self, "task_manager"):
                self.task_manager.emergency_stop()
            resp = "Stopped active operations."
            result = ToolResult(status=ExecutionStatus.SUCCESS, message=resp)
            self.context_manager.record_turn_result(resp)
            return resp, result

        if intent.intent_type == IntentType.UNKNOWN:
            result = ToolResult(
                status=ExecutionStatus.NOT_FOUND,
                message="I don't understand that command yet.",
                error="Unknown intent",
            )
            return "I don't understand that command yet.", result

        tool_request = self.router.route(intent)
        tool_result = self.executor.execute(tool_request)
        response_text = self._format_response(tool_result)
        self.context_manager.record_turn_result(response_text, tool_request.tool_name, tool_result.data)
        return response_text, tool_result


    def _format_response(self, result: ToolResult) -> str:
        """Format ToolResult into a clean, truthful assistant response string."""
        if result.status == ExecutionStatus.SUCCESS and getattr(result, "verified", True):
            msg = result.message.strip()
            if msg.lower() in ("downloads opened.", "opened downloads folder."):
                return "Done. I've opened your Downloads folder."
            elif not msg.startswith("✓") and not msg.startswith("Done"):
                return f"Done. {msg}"
            return msg
        elif result.status == ExecutionStatus.DENIED:
            return f"Security authorization required: {result.message}"
        else:
            reason = result.error or result.message or "Execution or verification failed."
            return f"I couldn't complete that action: {reason}"



    def shutdown(self) -> None:
        """Shutdown background subsystems and timers."""
        if hasattr(self, "automation_manager"):
            self.automation_manager.stop_all_automations()


