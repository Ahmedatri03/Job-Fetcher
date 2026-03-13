"""Abstract base class for all job-offer scoring strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

from config import JobOffer


class BaseScorer(ABC):
    """Base scorer interface.

    Every concrete scorer must implement :meth:`score` and return an integer
    between 0 and 100 (inclusive).
    """

    @abstractmethod
    def score(self, job: JobOffer) -> int:
        """Return a relevance score between 0 and 100."""
