from src.vision.ocr.mock_provider import MockOCRProvider
from src.vision.types import Screenshot, VisualSourceType



def test_mock_ocr_provider():
    provider = MockOCRProvider()

    shot_code = Screenshot(
        id="test_1",
        file_path="dummy.png",
        width=1000,
        height=800,
        source_type=VisualSourceType.WINDOW,
        window_title="main.py - VS Code",
    )
    result_code = provider.extract_text(shot_code)

    assert "SyntaxError" in result_code.full_text
    assert len(result_code.regions) > 0

    shot_general = Screenshot(
        id="test_2",
        file_path="dummy.png",
        width=1000,
        height=800,
        source_type=VisualSourceType.SCREEN,
    )
    result_gen = provider.extract_text(shot_general)
    assert "Save" in result_gen.full_text
