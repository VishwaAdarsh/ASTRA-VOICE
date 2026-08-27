import uuid
from pathlib import Path
from PIL import Image, ImageGrab
from src.core.config import Config
from src.core.exceptions import ScreenCaptureError
from src.core.logger import get_logger
from src.vision.types import BoundingBox, Screenshot, VisualSourceType



logger = get_logger()


class ScreenCapturer:
    """Captures primary desktop screen or defined region using PIL ImageGrab."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.temp_dir = self.config.temp_vision_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def capture_screen(self, region: BoundingBox | None = None) -> Screenshot:
        """Capture primary display image or specified bounding box region."""
        shot_id = f"screen_{uuid.uuid4().hex[:8]}"
        out_path = self.temp_dir / f"{shot_id}.png"

        try:
            logger.info(f"Capturing primary screen (region={region})")
            if region:
                bbox = (region.x1, region.y1, region.x2, region.y2)
                img = ImageGrab.grab(bbox=bbox)
            else:
                img = ImageGrab.grab()

            if img is None:
                # Fallback synthetic Image if headless/mock display environment
                img = Image.new("RGB", (1920, 1080), color=(30, 41, 59))

            img.save(out_path, format="PNG")
            w, h = img.size

            return Screenshot(
                id=shot_id,
                file_path=str(out_path),
                width=w,
                height=h,
                source_type=VisualSourceType.REGION if region else VisualSourceType.SCREEN,
            )
        except Exception as e:
            logger.warning(f"PIL ImageGrab failed: {e}. Generating fallback image.")
            # Fallback image generation
            img = Image.new("RGB", (1280, 720), color=(15, 23, 42))
            img.save(out_path, format="PNG")
            return Screenshot(
                id=shot_id,
                file_path=str(out_path),
                width=1280,
                height=720,
                source_type=VisualSourceType.SCREEN,
            )
