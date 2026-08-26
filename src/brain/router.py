"""
Intent Router.
Maps recognized intents into structured ToolRequests for tool execution.
The router does NOT execute tools directly.
"""

from src.brain.models import Intent, IntentType, ToolRequest
from src.core.exceptions import IntentRecognitionError
from src.core.logger import get_logger

logger = get_logger()


class IntentRouter:
    """Routes recognized Intents to specific ToolRequests."""

    INTENT_TOOL_MAP = {
        IntentType.OPEN_APPLICATION: "open_application",
        IntentType.OPEN_FOLDER: "open_folder",
        IntentType.OPEN_WEBSITE: "open_website",
        IntentType.SYSTEM_INFORMATION: "system_information",
    }

    def route(self, intent: Intent) -> ToolRequest:
        """Map intent to a structured ToolRequest."""
        if intent.intent_type == IntentType.UNKNOWN:
            logger.warning(f"Routing failed for unknown intent: '{intent.raw_command}'")
            raise IntentRecognitionError(
                f"Could not route command '{intent.raw_command}': Unknown intent."
            )

        tool_name = self.INTENT_TOOL_MAP.get(intent.intent_type)
        if not tool_name:
            logger.error(f"No tool registered for intent type: {intent.intent_type}")
            raise IntentRecognitionError(
                f"No tool mapping configured for intent type '{intent.intent_type}'."
            )

        logger.info(f"Routed intent '{intent.intent_type}' to tool '{tool_name}'")
        return ToolRequest(
            tool_name=tool_name,
            parameters=intent.parameters,
            intent=intent,
        )
