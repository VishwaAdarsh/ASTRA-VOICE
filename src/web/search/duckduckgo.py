"""
DuckDuckGo Search Provider Implementation.
"""

import json
import urllib.parse
import urllib.request
from src.core.logger import get_logger
from src.web.models import SearchRequest, SearchResult, SourceType
from src.web.search.mock_provider import MockSearchProvider
from src.web.search.provider import SearchProvider

logger = get_logger()


class DuckDuckGoSearchProvider(SearchProvider):
    """DuckDuckGo web search provider."""

    def __init__(self, fallback: MockSearchProvider | None = None):
        self.fallback = fallback or MockSearchProvider()

    def search(self, request: SearchRequest) -> list[SearchResult]:
        query = request.query.strip()
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            logger.info(f"Executing DuckDuckGo web search for query '{query}'")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                html_text = resp.read().decode("utf-8", errors="ignore")

            # Simple regex search for DuckDuckGo HTML result snippets
            import re
            links = re.findall(r'<a class="result__url" href="([^"]+)">', html_text)
            titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html_text)

            results = []
            for i in range(min(len(links), request.limit)):
                raw_link = links[i].strip()
                raw_title = re.sub(r"<[^>]+>", "", titles[i]) if i < len(titles) else "Web Result"
                domain = urllib.parse.urlparse(raw_link).netloc or "web"

                results.append(
                    SearchResult(
                        title=raw_title,
                        url=raw_link,
                        snippet=f"Web search result for {query}",
                        domain=domain,
                        source_type=SourceType.GENERAL_WEB,
                    )
                )

            if results:
                return results

            logger.warning("DuckDuckGo HTML returned 0 parseable items. Using mock search fallback.")
            return self.fallback.search(request)

        except Exception as e:
            logger.warning(f"DuckDuckGo search encounter error: {e}. Falling back to MockSearchProvider.")
            return self.fallback.search(request)
