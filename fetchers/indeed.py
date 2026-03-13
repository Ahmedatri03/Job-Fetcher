"""Indeed France fetcher — scrapes job listings from fr.indeed.com."""

from __future__ import annotations

import uuid

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config import JobOffer
from fetchers.base import BaseFetcher, polite_sleep, random_headers
from utils import compute_hash

_BASE_URL = "https://fr.indeed.com/jobs"


class IndeedFetcher(BaseFetcher):
    """Fetch offers from Indeed France via scraping."""

    def __init__(self) -> None:
        super().__init__("Indeed")

    def fetch(self) -> list[JobOffer]:
        """Scrape Indeed France for all query/location combinations."""
        queries = self._build_search_queries()
        locations = self._build_location_queries()
        seen: set[str] = set()
        offers: list[JobOffer] = []

        for query in queries:
            for location in locations:
                try:
                    page_offers = self._search(query, location)
                    for offer in page_offers:
                        if offer.hash not in seen:
                            seen.add(offer.hash)
                            offers.append(offer)
                    polite_sleep(2.0, 4.0)
                except Exception:
                    self.logger.exception(
                        "Error searching '%s' in '%s'", query, location,
                    )

        self.logger.info("Indeed: collected %d unique offers", len(offers))
        return offers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
    )
    def _search(self, query: str, location: str) -> list[JobOffer]:
        """Scrape one page of Indeed results."""
        params = {
            "q": query,
            "l": location,
            "sc": "0kf:jtype(permanent);",
        }
        resp = requests.get(
            _BASE_URL, params=params, headers=random_headers(), timeout=20,
        )

        if resp.status_code == 403:
            self.logger.warning("Indeed: blocked (403) for '%s' in '%s'", query, location)
            return []
        if resp.status_code != 200:
            self.logger.warning("Indeed: HTTP %d for '%s'", resp.status_code, query)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        offers: list[JobOffer] = []

        for card in soup.select("div.job_seen_beacon, div.jobsearch-ResultsList > div"):
            title_el = card.select_one("h2 a, h2 span")
            company_el = card.select_one("[data-testid='company-name'], span.companyName")
            location_el = card.select_one("[data-testid='text-location'], div.companyLocation")
            link_el = card.select_one("a[href*='/rc/clk'], a[href*='/viewjob'], h2 a")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc = location_el.get_text(strip=True) if location_el else location

            if not title:
                continue

            href = link_el.get("href", "") if link_el else ""
            url = f"https://fr.indeed.com{href}" if href.startswith("/") else href

            offer = JobOffer(
                id=str(uuid.uuid4()),
                title=title,
                company=company,
                location=loc,
                contract_type="CDI",
                description="",
                url=url,
                date_posted="",
                source="Indeed",
                hash=compute_hash(title, company, loc),
            )
            offers.append(offer)

        self.logger.info("Indeed: %d offers for '%s' in '%s'", len(offers), query, location)
        return offers
