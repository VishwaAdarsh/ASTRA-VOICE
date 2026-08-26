"""
Unit tests for WebContentParser and WebFetcher.
"""

from unittest.mock import MagicMock, patch
from src.web.retrieval.fetcher import WebFetcher
from src.web.retrieval.parser import WebContentParser


def test_web_content_parser():
    html_sample = """
    <html>
        <head><title>Python 3.14 Highlights</title></head>
        <body>
            <script>alert('hidden script');</script>
            <nav><a href="#">Home</a></nav>
            <h1>Main Title</h1>
            <p>Python 3.14 introduces performance optimizations.</p>
        </body>
    </html>
    """
    title, headings, clean_text = WebContentParser.parse_html(html_sample)

    assert title == "Python 3.14 Highlights"
    assert "Main Title" in headings
    assert "hidden script" not in clean_text
    assert "performance optimizations" in clean_text


@patch("urllib.request.urlopen")
def test_web_fetcher_success(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.headers = {"Content-Type": "text/html"}
    mock_resp.read.return_value = b"<html><head><title>Test</title></head><body><p>Fetched content</p></body></html>"
    mock_resp.__enter__.return_value = mock_resp

    mock_urlopen.return_value = mock_resp

    fetcher = WebFetcher()
    doc = fetcher.fetch_url("https://example.com/test")

    assert doc.title == "Test"
    assert doc.domain == "example.com"
    assert "Fetched content" in doc.clean_text
