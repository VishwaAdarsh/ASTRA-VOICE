"""
Source Ranking and Deduplication Engine.
Applies official domain weights, query relevance scores, and URL deduplication.
"""

from src.web.models import SearchResult, Source, SourceType


class SourceRanker:
    """Ranks and converts search results into validated Source objects."""

    OFFICIAL_DOMAINS = {
        "python.org": 1.3,
        "docs.python.org": 1.4,
        "github.com": 1.2,
        "microsoft.com": 1.2,
        "wikipedia.org": 1.1,
    }

    def rank_and_deduplicate(self, search_results: list[SearchResult]) -> list[Source]:
        """Deduplicate results by URL and calculate weighted relevance scores."""
        seen_urls = set()
        sources: list[Source] = []
        source_id = 1

        for res in search_results:
            clean_url = res.url.split("#")[0].rstrip("/")
            if clean_url in seen_urls:
                continue

            seen_urls.add(clean_url)

            # Apply domain weight multiplier
            weight = self.OFFICIAL_DOMAINS.get(res.domain.lower(), 1.0)
            score = round(res.relevance_score * weight, 2)

            source = Source(
                id=source_id,
                title=res.title,
                url=res.url,
                domain=res.domain,
                snippet=res.snippet,
                source_type=res.source_type,
                relevance=score,
            )
            sources.append(source)
            source_id += 1

        # Sort descending by relevance score
        sources.sort(key=lambda s: s.relevance, reverse=True)
        return sources
