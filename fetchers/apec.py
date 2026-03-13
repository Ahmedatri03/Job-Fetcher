"""APEC fetcher — uses the APEC JSON API for cadre-level offers."""

from __future__ import annotations

import uuid
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config import JobOffer
from fetchers.base import BaseFetcher, polite_sleep, random_headers
from utils import compute_hash

_SEARCH_URL = "https://api.apec.fr/portail-offre/v2/offres"
_DETAIL_URL = "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{}"


class ApecFetcher(BaseFetcher):
    """Fetch offers from APEC via their JSON API."""

    def __init__(self) -> None:
        super().__init__("APEC")

    def fetch(self) -> list[JobOffer]:
        """Fetch offers from APEC for all query/location combinations."""
        queries = self._build_search_queries()
        locations = self._build_location_queries()
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
                    polite_sleep(1.5, 3.0)
                except Exception:
                    self.logger.exception(
                        "Error searching '%s' in '%s'", query, location,
                    )

        self.logger.info("APEC: collected %d unique offers", len(offers))
        return offers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
    )
    def _search(self, query: str, location: str) -> list[JobOffer]:
        """Query the APEC JSON API for one keyword+location pair."""
        payload = {
            "motsCles": query,
            "lieux": [{"libelle": location}],
            "typeContrat": ["101"],  # CDI
            "niveauExperience": ["1"],  # Débutant
            "range": "0,50",
        }
        headers = random_headers()
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"

        resp = requests.post(
            _SEARCH_URL, json=payload, headers=headers, timeout=20,
        )

        if resp.status_code != 200:
            self.logger.warning("APEC: HTTP %d for '%s'", resp.status_code, query)
            return []

        data = resp.json()
        raw_offers = data.get("resultats", [])
        return [self._map_offer(r, location) for r in raw_offers if r]

    @staticmethod
    def _map_offer(raw: dict[str, Any], fallback_location: str) -> JobOffer:
        """Map an APEC API result to a JobOffer."""
        title = raw.get("intitule", "")
        company = raw.get("nomCompagnie", "N/A")
        location = raw.get("lieux", fallback_location)
        if isinstance(location, list):
            location = location[0].get("libelle", fallback_location) if location else fallback_location
        description = raw.get("texteHtml", raw.get("description", ""))
        offer_id = raw.get("numeroOffre", "")
        url = _DETAIL_URL.format(offer_id) if offer_id else ""
        date_posted = raw.get("datePublication", "")
        salary = raw.get("salaireTexte", "")

        return JobOffer(
            id=str(uuid.uuid4()),
            title=title,
            company=company,
            location=location if isinstance(location, str) else fallback_location,
            contract_type="CDI",
            description=description,
            url=url,
            date_posted=date_posted,
            source="APEC",
            salary=salary,
            hash=compute_hash(title, company, location if isinstance(location, str) else fallback_location),
        )
