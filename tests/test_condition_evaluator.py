"""
Unit tests for ConditionEvaluator.
"""

from src.automation.evaluator import ConditionEvaluator
from src.automation.models import Condition, ConditionType


def test_condition_evaluator_file_exists(tmp_path):
    evaluator = ConditionEvaluator()
    evaluator.resolver.sandbox_root = tmp_path

    cond = Condition(type=ConditionType.FILE_EXISTS, parameters={"folder": "downloads", "query": "report"})

    # Target folder empty -> FALSE
    res1 = evaluator.evaluate(cond)
    assert res1 == False

    # Create matching file -> Edge Triggered TRUE
    (tmp_path / "report_1.pdf").write_text("dummy report")
    res2 = evaluator.evaluate(cond)
    assert res2 == True

    # Subsequent check while file remains -> FALSE (no new edge trigger)
    res3 = evaluator.evaluate(cond)
    assert res3 == False
