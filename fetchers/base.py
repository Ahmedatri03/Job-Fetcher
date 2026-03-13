"""Abstract base class and shared helpers for all fetchers."""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod

from config import LOG_LEVEL, PROFILE, JobOffer
from utils import setup_logger

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]


def random_headers() -> dict[str, str]:
    """Return HTTP headers with a random User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }


def polite_sleep(min_seconds: float = 1.0, max_seconds: float = 2.5) -> None:
    """Sleep for a random duration to be polite to servers."""
    time.sleep(random.uniform(min_seconds, max_seconds))


class BaseFetcher(ABC):
    """Every concrete fetcher must set *name* and implement :meth:`fetch`."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = setup_logger(name, LOG_LEVEL)

    @abstractmethod
    def fetch(self) -> list[JobOffer]:
        """Fetch job offers from the source and return them."""

    def _build_search_queries(self) -> list[str]:
        """Return a broad set of search keywords covering French/English titles and tech stacks."""
        return [
            "développeur",
            "ingénieur logiciel",
            "ingénieur développement",
            "ingénieur études",
            "software engineer",
            "developer",
            "full stack",
            ".NET C#",
            "React Node.js",
            "Python Django",
            "Power BI SQL",
            "data analyst",
        ]

    def _build_location_queries(self) -> list[str]:
        """Return the main target cities for geo-filtered searches."""
        paca = PROFILE["locations"]["paca"][:3]
        other = PROFILE["locations"]["other"]
        return paca + other
