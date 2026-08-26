"""
Mock Search Provider for deterministic unit testing and offline execution.
"""

from src.web.models import SearchRequest, SearchResult, SourceType
from src.web.search.provider import SearchProvider


class MockSearchProvider(SearchProvider):
    """Mock Search Provider returning deterministic search results."""

    def search(self, request: SearchRequest) -> list[SearchResult]:
        query_text = request.query.lower().strip()

        if "python 3.14" in query_text or "python" in query_text:
            return [
                SearchResult(
                    title="What's New In Python 3.14 — Python Documentation",
                    url="https://docs.python.org/3.14/whatsnew/3.14.html",
                    snippet="Python 3.14 features new language updates, deferred evaluation of annotations, and enhanced performance optimizations.",
                    domain="docs.python.org",
                    source_type=SourceType.OFFICIAL_DOCUMENTATION,
                    relevance_score=0.98,
                ),
                SearchResult(
                    title="Python 3.14 Release Notes & Schedule — Python.org",
                    url="https://www.python.org/downloads/release/python-3140/",
                    snippet="Official release documentation and downloadable binaries for Python 3.14.",
                    domain="python.org",
                    source_type=SourceType.OFFICIAL_DOCUMENTATION,
                    relevance_score=0.95,
                ),
                SearchResult(
                    title="Python 3.14 Preview & Key Highlights - Real Python",
                    url="https://realpython.com/python-314-preview/",
                    snippet="Comprehensive overview of Python 3.14 new features and syntax changes.",
                    domain="realpython.com",
                    source_type=SourceType.BLOG,
                    relevance_score=0.88,
                ),
            ][: request.limit]
        elif "ai agent" in query_text or "framework" in query_text:
            return [
                SearchResult(
                    title="Top AI Agent Frameworks for 2026 — GitHub",
                    url="https://github.com/topics/ai-agents",
                    snippet="Curated list of open-source autonomous AI agent frameworks and libraries.",
                    domain="github.com",
                    source_type=SourceType.GITHUB,
                    relevance_score=0.96,
                ),
                SearchResult(
                    title="Overview of AI Agent Architectures — Research Paper",
                    url="https://arxiv.org/abs/2401.00001",
                    snippet="Academic survey of modern multi-agent planning, tool invocation, and memory architectures.",
                    domain="arxiv.org",
                    source_type=SourceType.RESEARCH,
                    relevance_score=0.92,
                ),
            ][: request.limit]

        # Default fallback results
        return [
            SearchResult(
                title=f"Web Search Results for '{request.query}'",
                url=f"https://example.com/search?q={request.query}",
                snippet=f"Information regarding {request.query} retrieved from web resources.",
                domain="example.com",
                source_type=SourceType.GENERAL_WEB,
                relevance_score=0.80,
            )
        ][: request.limit]
