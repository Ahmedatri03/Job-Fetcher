"""LinkedIn fetcher — minimal scraper, expected to be unreliable."""

from __future__ import annotations

import uuid

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config import JobOffer
from fetchers.base import BaseFetcher, polite_sleep, random_headers
from utils import compute_hash

_BASE_URL = "https://www.linkedin.com/jobs/search/"


class LinkedInFetcher(BaseFetcher):
    """Minimal LinkedIn scraper — fragile, disabled by default."""

    def __init__(self) -> None:
        super().__init__("LinkedIn")

    def fetch(self) -> list[JobOffer]:
        """Attempt to scrape LinkedIn public job pages."""
        queries = self._build_search_queries()[:3]
        locations = ["France"]
        seen: set[str] = set()
        offers: list[JobOffer] = []

        for query in queries:
            for location in locations:
                try:
                    results = self._search(query, location)
                    for offer in results:
                        if offer.hash not in seen:
                            seen.add(offer.hash)
                            offers.append(offer)
                    polite_sleep(3.0, 6.0)
                except Exception:
                    self.logger.exception(
                        "Error searching '%s' in '%s'", query, location,
                    )

        self.logger.info("LinkedIn: collected %d offers", len(offers))
        return offers

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=3, max=10),
    )
    def _search(self, query: str, location: str) -> list[JobOffer]:
        """Scrape one LinkedIn search page."""
        params = {
            "keywords": query,
            "location": location,
            "f_TPR": "r604800",  # last 7 days
            "f_JT": "F",  # full-time
        }
        resp = requests.get(
            _BASE_URL, params=params, headers=random_headers(), timeout=20,
        )

        if resp.status_code in (403, 429, 999):
            self.logger.warning("LinkedIn: blocked (%d)", resp.status_code)
            return []
        if resp.status_code != 200:
            self.logger.warning("LinkedIn: HTTP %d", resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        offers: list[JobOffer] = []

        for card in soup.select("div.base-card"):
            title_el = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle")
            location_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc = location_el.get_text(strip=True) if location_el else ""
            url = link_el.get("href", "") if link_el else ""

            if not title:
                continue

            offers.append(JobOffer(
                id=str(uuid.uuid4()),
                title=title,
                company=company,
                location=loc,
                contract_type="",
                description="",
                url=url,
                date_posted="",
                source="LinkedIn",
                hash=compute_hash(title, company, loc),
            ))

        self.logger.info("LinkedIn: %d offers for '%s'", len(offers), query)
        return offers
