from src.vision.types import BoundingBox, ElementType, OCRResult, Screenshot, VisualElement



class UIDetector:
    """Detects UI elements and bounding box regions from screenshot and OCR data."""

    def detect_elements(self, screenshot: Screenshot, ocr_result: OCRResult) -> list[VisualElement]:
        """Detect and classify UI elements."""
        elements: list[VisualElement] = []
        elem_id = 1

        for region in ocr_result.regions:
            label = region.text.strip()
            label_lower = label.lower()

            # Classify element type based on OCR label patterns
            if label_lower in ("save", "cancel", "submit", "ok", "run", "edit", "delete", "add"):
                elem_type = ElementType.BUTTON
            elif "input" in label_lower or "search" in label_lower:
                elem_type = ElementType.INPUT
            elif "http" in label_lower or ".com" in label_lower or ".org" in label_lower:
                elem_type = ElementType.LINK
            else:
                elem_type = ElementType.TEXT

            element = VisualElement(
                id=elem_id,
                element_type=elem_type,
                label=label,
                bounds=region.bounds,
                confidence=region.confidence,
                text=label,
                state="VISIBLE",
            )
            elements.append(element)
            elem_id += 1

        return elements
