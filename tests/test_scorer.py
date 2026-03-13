"""Tests for scoring.keyword_scorer.KeywordScorer."""

from __future__ import annotations

import pytest

from config import JobOffer
from scoring import KeywordScorer


def _make_job(**overrides) -> JobOffer:
    """Factory helper — creates a JobOffer with sensible defaults."""
    defaults = {
        "id": "test-1",
        "title": "Développeur",
        "company": "Acme",
        "location": "Marseille",
        "contract_type": "CDI",
        "description": "",
        "url": "https://example.com",
        "date_posted": "2026-03-01",
        "source": "test",
    }
    defaults.update(overrides)
    return JobOffer(**defaults)


class TestKeywordScorer:
    """Suite for KeywordScorer.score()."""

    def setup_method(self) -> None:
        self.scorer = KeywordScorer()

    def test_perfect_job_scores_high(self) -> None:
        """A job matching title + skills + junior + location should score >= 80."""
        job = _make_job(
            title="Développeur Backend Junior",
            description=(
                "Nous recherchons un développeur junior maîtrisant C#, .NET, "
                "Python, Node.js, Django. Vous travaillerez avec React, TypeScript, "
                "JavaScript sur des API REST et microservices backend. "
                "Compétences SQL, Power BI, MongoDB, PostgreSQL appréciées. "
                "Connaissance OpenAI et LLM un plus. "
                "Première expérience acceptée. 0-2 ans d'expérience."
            ),
            location="Marseille",
        )
        score = self.scorer.score(job)
        assert score >= 80, f"Expected >= 80, got {score}"

    def test_no_match_scores_zero(self) -> None:
        """A job with no matching keywords at all should score 0."""
        job = _make_job(
            title="Boulanger pâtissier",
            description="Fabrication de pains et viennoiseries.",
            location="Strasbourg",
        )
        score = self.scorer.score(job)
        assert score == 0, f"Expected 0, got {score}"

    def test_penalty_reduces_score(self) -> None:
        """Presence of 'confirmé' should reduce the score compared to the same job without it."""
        base = _make_job(
            title="Développeur Backend",
            description="Python API REST SQL junior",
            location="Marseille",
        )
        penalised = _make_job(
            title="Développeur Backend",
            description="Python API REST SQL junior confirmé",
            location="Marseille",
        )
        base_score = self.scorer.score(base)
        pen_score = self.scorer.score(penalised)
        assert pen_score < base_score, (
            f"Penalised ({pen_score}) should be lower than base ({base_score})"
        )

    def test_score_clamped_0_100(self) -> None:
        """Score must always be in [0, 100] regardless of input."""
        low = _make_job(
            title="Directeur Senior Lead",
            description="10 ans d'expérience confirmé expérimenté 7 ans 5 ans d'expérience",
            location="Nowhere",
        )
        high = _make_job(
            title="Développeur Backend Junior Full Stack .NET Python",
            description=(
                "C# .NET Node.js Python Django React TypeScript JavaScript "
                "API REST microservices SQL Power BI DAX MongoDB PostgreSQL "
                "OpenAI LLM junior 0-2 ans jeune diplômé première expérience"
            ),
            location="Marseille",
        )
        assert 0 <= self.scorer.score(low) <= 100
        assert 0 <= self.scorer.score(high) <= 100
