"""
Web Content Fetcher.
Performs size-bounded HTTP GET requests and extracts WebDocument representations.
"""

import urllib.parse
import urllib.request
from src.core.config import Config
from src.core.exceptions import WebFetchError
from src.core.logger import get_logger
from src.web.models import WebDocument
from src.web.retrieval.parser import WebContentParser
from src.web.retrieval.url_policy import URLPolicy

logger = get_logger()


class WebFetcher:
    """Retrieves and parses webpage content within strict security and size bounds."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.max_bytes = int(self.config.max_fetch_size_mb * 1024 * 1024)

    def fetch_url(self, url: str) -> WebDocument:
        """Validate URL policy, fetch content with size caps, and extract clean text."""
        valid_url = URLPolicy.validate_url(url)
        domain = urllib.parse.urlparse(valid_url).netloc or "web"

        headers = {
            "User-Agent": "ASTRA-Assistant/1.0 (Windows NT 10.0; Personal AI Computer Assistant)"
        }

        try:
            logger.info(f"Fetching webpage content for URL '{valid_url}'")
            req = urllib.request.Request(valid_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                content_type = resp.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "text/plain" not in content_type and "application/xhtml" not in content_type:
                    logger.warning(f"Non-text Content-Type '{content_type}' for URL '{valid_url}'. Returning mock summary.")
                    return WebDocument(
                        url=valid_url,
                        title=domain,
                        domain=domain,
                        clean_text=f"Content retrieved from {domain}.",
                    )

                raw_bytes = resp.read(self.max_bytes)
                html_text = raw_bytes.decode("utf-8", errors="ignore")

            title, headings, clean_text = WebContentParser.parse_html(html_text)

            return WebDocument(
                url=valid_url,
                title=title,
                domain=domain,
                clean_text=clean_text[:4000],  # Truncate to max 4000 chars
                headings=headings,
                content_length=len(clean_text),
            )

        except Exception as e:
            logger.error(f"WebFetcher failed for '{url}': {e}")
            raise WebFetchError(f"Failed to fetch webpage '{url}': {e}")
