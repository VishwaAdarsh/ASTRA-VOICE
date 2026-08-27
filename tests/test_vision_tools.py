"""
Integration tests for Phase 8 Vision Tools (AnalyzeScreenTool, AnalyzeActiveWindowTool, AnalyzeImageTool, ReadScreenTextTool).
"""

from PIL import Image
from src.brain.models import ExecutionStatus, PermissionLevel
from src.tools.vision.image import AnalyzeImageTool
from src.tools.vision.read_text import ReadScreenTextTool
from src.tools.vision.screen import AnalyzeScreenTool
from src.tools.vision.window import AnalyzeActiveWindowTool


def test_vision_tools_execution(tmp_path):
    analyze_screen = AnalyzeScreenTool()
    analyze_window = AnalyzeActiveWindowTool()
    read_text = ReadScreenTextTool()
    analyze_image = AnalyzeImageTool()

    assert analyze_screen.permission_level == PermissionLevel.SAFE
    assert analyze_window.permission_level == PermissionLevel.SAFE
    assert read_text.permission_level == PermissionLevel.SAFE
    assert analyze_image.permission_level == PermissionLevel.SAFE

    # 1. Analyze Screen
    res_screen = analyze_screen.execute({})
    assert res_screen.status == ExecutionStatus.SUCCESS
    assert "description" in res_screen.data

    # 2. Analyze Active Window
    res_window = analyze_window.execute({})
    assert res_window.status == ExecutionStatus.SUCCESS

    # 3. Read Screen Text
    res_read = read_text.execute({})
    assert res_read.status == ExecutionStatus.SUCCESS
    assert "text" in res_read.data

    # 4. Analyze Image
    test_img_path = tmp_path / "test.png"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(test_img_path)

    res_img = analyze_image.execute({"image_path": str(test_img_path)})
    assert res_img.status == ExecutionStatus.SUCCESS
