"""Welcome to the Jungle fetcher — scrapes WTTJ job listings."""

from __future__ import annotations

import uuid

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config import JobOffer
from fetchers.base import BaseFetcher, polite_sleep, random_headers
from utils import compute_hash

_BASE_URL = "https://www.welcometothejungle.com/fr/jobs"

_CITY_COORDS = {
    "Aix-en-Provence": (43.5297, 5.4474),
    "Marseille": (43.2965, 5.3698),
    "Paris": (48.8566, 2.3522),
    "Lyon": (45.7640, 4.8357),
    "Montpellier": (43.6108, 3.8767),
    "Nice": (43.7102, 7.2620),
}


class WTTJFetcher(BaseFetcher):
    """Fetch offers from Welcome to the Jungle."""

    def __init__(self) -> None:
        super().__init__("WTTJ")

    def fetch(self) -> list[JobOffer]:
        """Fetch job offers from WTTJ for all query/location combinations."""
        queries = self._build_search_queries()
        seen: set[str] = set()
        offers: list[JobOffer] = []

        for query in queries:
            for city, (lat, lng) in _CITY_COORDS.items():
                try:
                    page_offers = self._search(query, lat, lng, city)
                    for offer in page_offers:
                        if offer.hash not in seen:
                            seen.add(offer.hash)
                            offers.append(offer)
                    polite_sleep(1.5, 3.0)
                except Exception:
                    self.logger.exception("Error searching '%s' near %s", query, city)

        self.logger.info("WTTJ: collected %d unique offers", len(offers))
        return offers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
    )
    def _search(self, query: str, lat: float, lng: float, city: str) -> list[JobOffer]:
        """Scrape one page of WTTJ results."""
        params = {
            "query": query,
            "page": "1",
            "aroundLatLng": f"{lat},{lng}",
            "aroundRadius": "40000",
        }
        resp = requests.get(
            _BASE_URL, params=params, headers=random_headers(), timeout=20,
        )
        if resp.status_code != 200:
            self.logger.warning("WTTJ returned %d for '%s'", resp.status_code, query)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        offers: list[JobOffer] = []

        for card in soup.select("a[href*='/fr/companies/']"):
            href = card.get("href", "")
            if "/jobs/" not in href:
                continue

            title = card.get_text(strip=True)
            if not title:
                continue

            url = f"https://www.welcometothejungle.com{href}" if href.startswith("/") else href

            company = ""
            parts = href.split("/companies/")
            if len(parts) > 1:
                company = parts[1].split("/")[0].replace("-", " ").title()

            offer = JobOffer(
                id=str(uuid.uuid4()),
                title=title,
                company=company,
                location=city,
                contract_type="CDI",
                description="",
                url=url,
                date_posted="",
                source="WTTJ",
                hash=compute_hash(title, company, city),
            )
            offers.append(offer)

        self.logger.info("WTTJ: %d offers for '%s' near %s", len(offers), query, city)
        return offers
