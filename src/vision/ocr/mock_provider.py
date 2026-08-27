from src.vision.ocr.provider import OCRProvider
from src.vision.types import BoundingBox, OCRRegion, OCRResult, Screenshot



class MockOCRProvider(OCRProvider):
    """Mock OCR Provider returning simulated OCR text extraction results."""

    def extract_text(self, screenshot: Screenshot) -> OCRResult:
        title = (screenshot.window_title or "").lower()

        if "code" in title or "astra" in title:
            text = "VS Code Terminal: SyntaxError: invalid syntax in src/brain/agent.py at line 147"
            regions = [
                OCRRegion(text="VS Code Terminal", bounds=BoundingBox(x1=50, y1=50, x2=250, y2=80), confidence=0.98),
                OCRRegion(text="SyntaxError: invalid syntax", bounds=BoundingBox(x1=50, y1=100, x2=450, y2=130), confidence=0.95),
            ]
        elif "chrome" in title or "browser" in title:
            text = "Python 3.14 Release Notes — Official Documentation"
            regions = [
                OCRRegion(text="Python 3.14 Release Notes", bounds=BoundingBox(x1=100, y1=60, x2=500, y2=90), confidence=0.99),
            ]
        else:
            text = "ASTRA Assistant Desktop UI: [Save] [Cancel] Settings Status: Ready"
            regions = [
                OCRRegion(text="Save", bounds=BoundingBox(x1=200, y1=400, x2=280, y2=440), confidence=0.96),
                OCRRegion(text="Cancel", bounds=BoundingBox(x1=300, y1=400, x2=380, y2=440), confidence=0.96),
            ]

        return OCRResult(full_text=text, regions=regions, confidence=0.95, language="en")
