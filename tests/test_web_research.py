"""
Unit tests for Web Search, Source Ranking, and Research Synthesizer.
"""

from src.web.models import SearchRequest, SourceType
from src.web.research.researcher import WebResearcher
from src.web.research.synthesizer import ResearchSynthesizer
from src.web.search.mock_provider import MockSearchProvider
from src.web.sources.ranking import SourceRanker


def test_mock_search_provider():
    provider = MockSearchProvider()
    req = SearchRequest(query="Python 3.14", limit=2)
    results = provider.search(req)

    assert len(results) == 2
    assert "Python 3.14" in results[0].title
    assert results[0].domain == "docs.python.org"


def test_source_ranker_and_deduplication():
    provider = MockSearchProvider()
    ranker = SourceRanker()

    results = provider.search(SearchRequest(query="Python 3.14", limit=5))
    sources = ranker.rank_and_deduplicate(results)

    assert len(sources) > 0
    # Official docs.python.org domain should rank highest
    assert sources[0].domain in ("docs.python.org", "python.org")


def test_research_synthesizer_and_citations():
    provider = MockSearchProvider()
    ranker = SourceRanker()
    synthesizer = ResearchSynthesizer()

    results = provider.search(SearchRequest(query="Python 3.14", limit=2))
    sources = ranker.rank_and_deduplicate(results)
    answer = synthesizer.synthesize("Python 3.14", sources)

    assert len(answer.sources) == 2
    assert "[1]" in answer.summary
    assert "[2]" in answer.summary


def test_web_researcher_end_to_end():
    researcher = WebResearcher(search_provider=MockSearchProvider())
    answer = researcher.research("AI Agent Frameworks", depth="QUICK")

    assert len(answer.sources) > 0
    assert "AI Agent Frameworks" in answer.summary
