"""
Web Content Parser and Extractor.
Strips page chrome (nav, footer, scripts, styles) to produce clean readable text and headings.
"""

import re
from typing import Any


class WebContentParser:
    """Parses raw HTML and extracts title, headings, and clean text."""

    @staticmethod
    def parse_html(html_text: str) -> tuple[str, list[str], str]:
        """Extract title, headings, and clean body text from HTML."""
        if not html_text:
            return "Untitled Page", [], ""

        # 1. Extract Title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "Web Page"

        # 2. Extract Headings (h1, h2, h3)
        headings_raw = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html_text, re.IGNORECASE | re.DOTALL)
        headings = [re.sub(r"<[^>]+>", "", h).strip() for h in headings_raw if h.strip()]

        # 3. Strip Scripts, Styles, Nav, Footer, Comments
        clean_html = re.sub(r"<(script|style|nav|footer|header|noscript)[^>]*>.*?</\1>", "", html_text, flags=re.IGNORECASE | re.DOTALL)
        clean_html = re.sub(r"<!--.*?-->", "", clean_html, flags=re.DOTALL)

        # 4. Convert tags to plain text
        text = re.sub(r"<[^>]+>", " ", clean_html)
        text = re.sub(r"\s+", " ", text).strip()

        return title, headings[:10], text
