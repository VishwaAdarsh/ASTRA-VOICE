"""
Research Synthesizer Engine.
Synthesizes retrieved sources into structured research answers with claim attribution and citations.
"""

from src.web.models import Claim, ResearchAnswer, Source


class ResearchSynthesizer:
    """Synthesizes web sources into structured answers with numbered citations."""

    def synthesize(self, objective: str, sources: list[Source]) -> ResearchAnswer:
        """Construct structured research summary with numbered citations [1], [2]."""
        if not sources:
            return ResearchAnswer(
                summary=f"No web sources found for '{objective}'.",
                key_points=[],
                claims=[],
                sources=[],
                uncertainties=["No verified sources were retrieved."],
            )

        key_points = []
        claims = []

        for idx, src in enumerate(sources, start=1):
            claim_text = f"{src.snippet} [{idx}]"
            claims.append(Claim(text=claim_text, source_ids=[src.id], claim_type="FACT"))
            key_points.append(f"{src.title} — {src.snippet} [{idx}]")

        summary = f"Research summary for '{objective}':\n" + "\n".join([f"• {kp}" for kp in key_points])

        return ResearchAnswer(
            summary=summary,
            key_points=key_points,
            claims=claims,
            sources=sources,
            uncertainties=[],
        )
