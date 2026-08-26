"""
Integration tests for Phase 6 Web Tools (SearchWebTool, FetchWebpageTool, ResearchTopicTool).
"""

from unittest.mock import MagicMock, patch
from src.brain.models import ExecutionStatus, PermissionLevel
from src.tools.web.fetch import FetchWebpageTool
from src.tools.web.research import ResearchTopicTool
from src.tools.web.search import SearchWebTool
from src.web.models import WebDocument
from src.web.search.mock_provider import MockSearchProvider


def test_search_web_tool():
    tool = SearchWebTool(provider=MockSearchProvider())
    assert tool.permission_level == PermissionLevel.SAFE
    assert tool.validate({"query": "Python 3.14"})

    res = tool.execute({"query": "Python 3.14"})
    assert res.status == ExecutionStatus.SUCCESS
    assert res.data["count"] > 0
    assert "results" in res.data


@patch("src.web.retrieval.fetcher.WebFetcher.fetch_url")
def test_fetch_webpage_tool(mock_fetch):
    mock_doc = WebDocument(
        url="https://docs.python.org/3.14/",
        title="Python 3.14 Docs",
        domain="docs.python.org",
        clean_text="Python 3.14 documentation main page.",
    )
    mock_fetch.return_value = mock_doc

    tool = FetchWebpageTool()
    res = tool.execute({"url": "https://docs.python.org/3.14/"})

    assert res.status == ExecutionStatus.SUCCESS
    assert res.data["domain"] == "docs.python.org"
    assert "Python 3.14" in res.data["content"]


def test_research_topic_tool():
    tool = ResearchTopicTool()
    res = tool.execute({"topic": "AI Agents", "depth": "QUICK"})

    assert res.status == ExecutionStatus.SUCCESS
    assert "summary" in res.data
    assert len(res.data["sources"]) > 0
