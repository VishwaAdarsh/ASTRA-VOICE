from src.vision.analysis.analyzer import VisualAnalyzer
from src.vision.analysis.ui_detection import UIDetector
from src.vision.context.builder import VisualContextBuilder
from src.vision.types import ElementType, Screenshot, VisualSourceType



def test_ui_detector_classification():
    detector = UIDetector()
    shot = Screenshot(id="t1", file_path="dummy.png", width=800, height=600, source_type=VisualSourceType.SCREEN)

    analyzer = VisualAnalyzer()
    context = analyzer.analyze_screenshot(shot)

    assert len(context.elements) > 0
    btn_elements = [e for e in context.elements if e.element_type == ElementType.BUTTON]
    assert len(btn_elements) > 0


def test_visual_analyzer_error_detection():
    analyzer = VisualAnalyzer()
    shot = Screenshot(
        id="t2",
        file_path="dummy.png",
        width=800,
        height=600,
        source_type=VisualSourceType.WINDOW,
        window_title="main.py - VS Code",
    )
    context = analyzer.analyze_screenshot(shot)

    assert len(context.detected_errors) > 0
    assert any("SyntaxError" in err for err in context.detected_errors)


def test_visual_context_builder_prompt():
    builder = VisualContextBuilder()
    analyzer = VisualAnalyzer()
    shot = Screenshot(id="t3", file_path="dummy.png", width=800, height=600, source_type=VisualSourceType.SCREEN)

    context = analyzer.analyze_screenshot(shot)
    prompt = builder.build_prompt_summary(context)

    assert "VISUAL CONTEXT DATA" in prompt
    assert "Detected UI Elements" in prompt
