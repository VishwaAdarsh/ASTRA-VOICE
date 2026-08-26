"""
User Confirmation Handlers for CONFIRM permission level tools.
"""

from abc import ABC, abstractmethod


class ConfirmationHandler(ABC):
    """Abstract interface for prompting user confirmation."""

    @abstractmethod
    def confirm(self, action_description: str) -> bool:
        """Prompt user for confirmation."""
        pass


class ConsoleConfirmationHandler(ConfirmationHandler):
    """CLI prompt implementation of ConfirmationHandler."""

    def confirm(self, action_description: str) -> bool:
        try:
            response = input(f"ASTRA Security Prompt: Allow '{action_description}'? [y/N]: ")
            return response.strip().lower() in ("y", "yes")
        except EOFError:
            return False


class AutoApproveConfirmationHandler(ConfirmationHandler):
    """Testing handler that auto-approves confirmation prompts."""

    def __init__(self, approve: bool = True):
        self.approve = approve

    def confirm(self, action_description: str) -> bool:
        return self.approve
