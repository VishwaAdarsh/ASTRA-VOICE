"""
Web Researcher Orchestrator.
Coordinates search providers, web fetcher, source ranking, and synthesis for multi-source research tasks.
"""

from src.core.config import Config
from src.core.logger import get_logger
from src.web.models import ResearchAnswer, ResearchPlan, ResearchStep, SearchRequest
from src.web.research.synthesizer import ResearchSynthesizer
from src.web.search.factory import SearchProviderFactory
from src.web.search.provider import SearchProvider
from src.web.sources.ranking import SourceRanker

logger = get_logger()


class WebResearcher:
    """Orchestrates end-to-end web research tasks."""

    def __init__(
        self,
        config: Config | None = None,
        search_provider: SearchProvider | None = None,
        ranker: SourceRanker | None = None,
        synthesizer: ResearchSynthesizer | None = None,
    ):
        self.config = config or Config()
        self.search_provider = search_provider or SearchProviderFactory.create(self.config)
        self.ranker = ranker or SourceRanker()
        self.synthesizer = synthesizer or ResearchSynthesizer()

    def research(self, topic: str, depth: str = "STANDARD") -> ResearchAnswer:
        """Execute web research for topic at specified depth (QUICK, STANDARD, DEEP)."""
        logger.info(f"WEB_RESEARCH_STARTED: topic='{topic}', depth='{depth}'")

        limit = 3 if depth == "QUICK" else (5 if depth == "STANDARD" else 8)
        req = SearchRequest(query=topic, limit=limit)

        # 1. Search
        search_results = self.search_provider.search(req)

        # 2. Rank & Deduplicate Sources
        sources = self.ranker.rank_and_deduplicate(search_results)

        # 3. Synthesize Research Answer
        answer = self.synthesizer.synthesize(topic, sources)
        logger.info(f"WEB_RESEARCH_COMPLETED: topic='{topic}', sources={len(answer.sources)}")

        return answer
