"""
Web Intelligence & Research Engine Domain Models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    """Classification type for web sources."""

    GENERAL_WEB = "GENERAL_WEB"
    OFFICIAL_DOCUMENTATION = "OFFICIAL_DOCUMENTATION"
    NEWS = "NEWS"
    BLOG = "BLOG"
    REFERENCE = "REFERENCE"
    RESEARCH = "RESEARCH"
    GITHUB = "GITHUB"
    OTHER = "OTHER"


@dataclass
class SearchRequest:
    """Request payload for web search queries."""

    query: str
    limit: int = 5
    recency: str = "recent"
    domain_filters: list[str] = field(default_factory=list)
    safe_search: bool = True


@dataclass
class SearchResult:
    """Individual web search result item."""

    title: str
    url: str
    snippet: str
    domain: str
    published_at: str | None = None
    source_type: SourceType = SourceType.GENERAL_WEB
    relevance_score: float = 1.0


@dataclass
class WebDocument:
    """Retrieved webpage document container."""

    url: str
    title: str
    domain: str
    clean_text: str
    headings: list[str] = field(default_factory=list)
    retrieved_at: datetime = field(default_factory=datetime.now)
    content_length: int = 0


@dataclass
class Source:
    """Sourced research reference item."""

    id: int
    title: str
    url: str
    domain: str
    snippet: str
    content: str = ""
    source_type: SourceType = SourceType.GENERAL_WEB
    relevance: float = 1.0


@dataclass
class Claim:
    """Individual factual claim extracted during research."""

    text: str
    source_ids: list[int] = field(default_factory=list)
    claim_type: str = "FACT"  # 'FACT', 'INFERENCE', 'OPINION'


@dataclass
class ResearchStep:
    """Single step in a multi-query research plan."""

    step_id: int
    query: str
    purpose: str
    status: str = "PENDING"
    results: list[SearchResult] = field(default_factory=list)


@dataclass
class ResearchPlan:
    """Multi-query research plan."""

    plan_id: str
    objective: str
    depth: str = "STANDARD"  # 'QUICK', 'STANDARD', 'DEEP'
    steps: list[ResearchStep] = field(default_factory=list)


@dataclass
class ResearchAnswer:
    """Final synthesized research response with source citations."""

    summary: str
    key_points: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
