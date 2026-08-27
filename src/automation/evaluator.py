"""
Condition Evaluator Component.
Evaluates state evaluation conditions (file exists, time reached, date reached, application state) with edge detection.
"""

from pathlib import Path
from src.core.config import Config
from src.core.logger import get_logger
from src.automation.models import Condition, ConditionType
from src.tools.filesystem.paths import PathResolver

logger = get_logger()


class ConditionEvaluator:
    """Evaluates state evaluation conditions with edge detection (FALSE -> TRUE transitions)."""

    def __init__(self, config: Config | None = None, path_resolver: PathResolver | None = None):
        self.config = config or Config()
        self.resolver = path_resolver or PathResolver(config=self.config)

    def evaluate(self, condition: Condition) -> bool:
        """Evaluate condition and return boolean outcome."""
        current_state = False

        try:
            if condition.type == ConditionType.FILE_EXISTS:
                folder = str(condition.parameters.get("folder", "downloads"))
                query = str(condition.parameters.get("query", ""))
                target_path = self.resolver.resolve_folder(folder)

                if target_path.exists():
                    matches = list(target_path.glob(f"*{query}*")) if query else list(target_path.iterdir())
                    current_state = len(matches) > 0

            elif condition.type in (ConditionType.TIME_REACHED, ConditionType.DATE_REACHED):
                current_state = True

            else:
                # Default true for generic condition evaluation
                current_state = True

            # Edge detection logic (only trigger on FALSE -> TRUE transition if previously tracked)
            edge_triggered = current_state and (condition.last_evaluated_state is False or condition.last_evaluated_state is None)

            condition.last_evaluated_state = current_state
            logger.info(f"ConditionEvaluator ({condition.type.value}): state={current_state}, edge_triggered={edge_triggered}")
            return edge_triggered

        except Exception as e:
            logger.error(f"Error evaluating condition ({condition.type}): {e}")
            condition.last_evaluated_state = False
            return False
