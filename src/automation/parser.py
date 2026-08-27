"""
Automation Parser Component.
Translates natural language text requests into structured AutomationDraft definitions.
"""

import re
from src.core.config import Config
from src.core.logger import get_logger
from src.automation.models import ActionType, AutomationDraft, ConditionType, TriggerType

logger = get_logger()


class AutomationParser:
    """Parses natural language requests into structured AutomationDrafts."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()

    def parse_request(self, user_text: str) -> AutomationDraft:
        """Parse natural language command into structured AutomationDraft."""
        text = user_text.strip().lower()
        logger.info(f"AutomationParser parsing request: '{user_text}'")

        # 1. Pattern: Reminder Schedule ("remind me at 8 PM to...", "remind me tomorrow morning")
        if "remind" in text:
            name = user_text
            time_str = "09:00"
            if "8 pm" in text or "20:00" in text or "8pm" in text:
                time_str = "20:00"
            elif "9 am" in text or "09:00" in text or "9am" in text:
                time_str = "09:00"
            elif "morning" in text:
                time_str = self.config.quiet_hours_end  # Default morning after quiet hours

            recurrence = "NONE"
            if "every day" in text or "daily" in text:
                recurrence = "DAILY"
            elif "every monday" in text or "weekly" in text:
                recurrence = "WEEKLY"

            return AutomationDraft(
                name=f"Reminder: {user_text}",
                description=f"Scheduled reminder created from: '{user_text}'",
                trigger_type=TriggerType.SCHEDULE,
                trigger_config={"time": time_str, "recurrence": recurrence},
                action_config={"type": ActionType.NOTIFY.value, "tool": "system_info", "arguments": {"message": user_text}},
            )

        # 2. Pattern: Condition Watch ("tell me when a new report appears in downloads")
        elif "tell me when" in text or "notify me when" in text or "check if" in text:
            target_folder = "downloads"
            if "documents" in text:
                target_folder = "documents"
            elif "desktop" in text:
                target_folder = "desktop"

            return AutomationDraft(
                name=f"Condition Watch: {user_text}",
                description=f"File condition watch created from: '{user_text}'",
                trigger_type=TriggerType.CONDITION,
                trigger_config={"interval_sec": 300},
                condition_config={"type": ConditionType.FILE_EXISTS.value, "parameters": {"folder": target_folder, "query": "report"}},
                action_config={"type": ActionType.NOTIFY.value, "tool": "system_info", "arguments": {"message": f"Condition met: {user_text}"}},
            )

        # 3. Pattern: Recurring Research ("every Friday research AI news")
        elif "research" in text and ("every" in text or "weekly" in text or "daily" in text):
            return AutomationDraft(
                name=f"Automated Research: {user_text}",
                description=f"Recurring research automation created from: '{user_text}'",
                trigger_type=TriggerType.SCHEDULE,
                trigger_config={"time": "18:00", "recurrence": "WEEKLY"},
                action_config={"type": ActionType.RUN_RESEARCH.value, "tool": "research_topic", "arguments": {"topic": "AI news"}},
            )

        # Fallback Default Draft
        return AutomationDraft(
            name=f"Automation: {user_text}",
            description=f"Automation created from: '{user_text}'",
            trigger_type=TriggerType.INTERVAL,
            trigger_config={"interval_sec": 3600},
            action_config={"type": ActionType.NOTIFY.value, "tool": "system_info", "arguments": {"message": user_text}},
        )
