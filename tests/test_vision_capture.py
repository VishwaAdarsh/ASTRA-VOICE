from pathlib import Path
from src.vision.capture.manager import CaptureManager
from src.vision.capture.screen import ScreenCapturer
from src.vision.capture.window import WindowCapturer
from src.vision.types import BoundingBox, VisualSourceType




def test_screen_capturer_capture(tmp_path):
    capturer = ScreenCapturer()
    capturer.temp_dir = tmp_path

    shot = capturer.capture_screen()
    assert shot.id.startswith("screen_")
    assert Path(shot.file_path).exists()
    assert shot.width > 0
    assert shot.height > 0
    assert shot.source_type == VisualSourceType.SCREEN


def test_window_capturer_capture(tmp_path):
    screen_cap = ScreenCapturer()
    screen_cap.temp_dir = tmp_path
    win_cap = WindowCapturer(screen_capturer=screen_cap)

    shot = win_cap.capture_active_window()
    assert shot.source_type == VisualSourceType.WINDOW
    assert Path(shot.file_path).exists()


def test_capture_manager_cleanup(tmp_path):
    mgr = CaptureManager()
    mgr.config.temp_vision_dir = tmp_path

    # Create dummy screenshot files
    (tmp_path / "screen_1.png").write_text("dummy image data")
    (tmp_path / "screen_2.png").write_text("dummy image data")

    cleaned = mgr.cleanup_temp_screenshots()
    assert cleaned == 2
    assert len(list(tmp_path.glob("*.png"))) == 0
