"""Keyword-based scoring engine for job offers."""

from __future__ import annotations

import re

from config import PROFILE, JobOffer
from scoring.base import BaseScorer
from utils import normalize, setup_logger

logger = setup_logger(__name__)


class KeywordScorer(BaseScorer):
    """Score a job offer by matching its text against the candidate profile.

    Scoring breakdown (rough weights):
      - Title match:     up to 30 pts
      - Skills match:    up to 40 pts
      - Junior keywords: up to 15 pts
      - Location bonus:  up to 15 pts
      - Penalties:       negative (experience-level keywords)
    """

    def __init__(self) -> None:
        self._titles: list[str] = [normalize(t) for t in PROFILE["target_titles"]]
        self._skills: dict[str, list[str]] = PROFILE["skills"]
        self._junior_kw: list[str] = [normalize(k) for k in PROFILE["junior_keywords"]]
        self._penalty_kw: dict[int, list[str]] = {
            int(k): [normalize(w) for w in v]
            for k, v in PROFILE["penalty_keywords"].items()
        }
        self._paca: list[str] = [c.lower() for c in PROFILE["locations"]["paca"]]
        self._other_locs: list[str] = [c.lower() for c in PROFILE["locations"]["other"]]

    def score(self, job: JobOffer) -> int:
        """Return a relevance score between 0 and 100."""
        title_lower = normalize(job.title)
        desc_lower = normalize(job.description)
        full_text = f"{title_lower} {desc_lower}"

        points = 0
        points += self._score_title(title_lower)
        points += self._score_skills(full_text)
        points += self._score_junior(full_text)
        points += self._score_location(job)
        points += self._score_penalties(full_text)

        return max(0, min(100, points))

    def _score_title(self, title: str) -> int:
        """Up to 30 points for matching target titles."""
        best = 0
        for target in self._titles:
            target_norm = normalize(target)
            if target_norm in title:
                best = max(best, 30)
            elif any(word in title for word in target_norm.split()):
                best = max(best, 15)
        return best

    def _score_skills(self, text: str) -> int:
        """Up to 40 points for skill-keyword matches across categories."""
        total = 0
        per_category = 40 / max(len(self._skills), 1)

        for _category, keywords in self._skills.items():
            matched = sum(1 for kw in keywords if kw.lower() in text)
            ratio = matched / max(len(keywords), 1)
            total += ratio * per_category

        return int(round(total))

    def _score_junior(self, text: str) -> int:
        """Up to 15 points if junior-friendly keywords are found."""
        matched = sum(1 for kw in self._junior_kw if kw in text)
        if matched >= 3:
            return 15
        if matched >= 1:
            return 10
        return 0

    def _score_location(self, job: JobOffer) -> int:
        """Up to 15 points based on location relevance."""
        loc = normalize(job.location)
        remote = normalize(job.remote_type)

        if any(city in loc for city in self._paca):
            return 15
        if "remote" in remote or "télétravail" in remote or "teletravail" in remote:
            return 12
        if any(city in loc for city in self._other_locs):
            return 8
        return 0

    def _score_penalties(self, text: str) -> int:
        """Apply negative adjustments for seniority/experience keywords."""
        penalty = 0
        for points, keywords in self._penalty_kw.items():
            for kw in keywords:
                if kw in text:
                    penalty += points
                    break
        return penalty
