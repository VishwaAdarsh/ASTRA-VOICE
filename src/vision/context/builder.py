from src.vision.types import VisualContext



class VisualContextBuilder:
    """Formats VisualContext into structured LLM prompt context."""

    def build_prompt_summary(self, context: VisualContext) -> str:
        """Format VisualContext into clean, untrusted data prompt text."""
        lines = [
            "=== VISUAL CONTEXT DATA ===",
            f"Source: {context.screenshot.source_type.value}",
            f"Application: {context.app_name}",
            f"Window Title: {context.window_title}",
            f"Visual Description: {context.description}",
        ]

        if context.detected_errors:
            lines.append("Detected Errors:")
            for err in context.detected_errors:
                lines.append(f"  • {err}")

        if context.ocr.full_text:
            lines.append("Extracted Text:")
            lines.append(f"  {context.ocr.full_text[:500]}")

        if context.elements:
            lines.append(f"Detected UI Elements ({len(context.elements)}):")
            for elem in context.elements[:8]:
                lines.append(f"  • [{elem.element_type.value}] {elem.label}")

        lines.append("==========================")
        return "\n".join(lines)
