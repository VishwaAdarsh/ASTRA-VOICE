"""
ASTRA Application Lifecycle Manager.
Handles system startup initialization and graceful shutdown sequences.
"""

from typing import TYPE_CHECKING
from src.core.config import Config
from src.core.logger import get_logger, setup_logger

if TYPE_CHECKING:
    from src.brain.agent import AstraAgent


class SystemLifecycle:
    """Manages application lifecycle states."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.logger = setup_logger(self.config.log_file, self.config.log_level)
        self.is_running = False

    def startup(self) -> "AstraAgent":
        """Initialize all core components and return the ready AstraAgent."""
        self.logger.info("Initializing ASTRA Phase 1 Foundation...")
        self.logger.info(f"Environment: {self.config.env}")
        self.logger.info(f"Log path: {self.config.log_file}")

        # Lazy import to avoid circular imports
        from src.brain.agent import AstraAgent
        agent = AstraAgent(config=self.config)
        self.is_running = True
        self.logger.info("ASTRA System startup complete. Ready for commands.")
        return agent

    def shutdown(self, agent: "AstraAgent | None" = None) -> None:
        """Perform a clean system shutdown."""
        if self.is_running:
            self.logger.info("Shutting down ASTRA system gracefully...")
            if agent:
                agent.shutdown()
            self.is_running = False
            self.logger.info("ASTRA System shutdown complete.")

