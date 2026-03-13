"""Fetcher for the France Travail (ex-Pôle Emploi) public API."""

from __future__ import annotations

import re
import uuid
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    FRANCE_TRAVAIL_CLIENT_ID,
    FRANCE_TRAVAIL_CLIENT_SECRET,
    JobOffer,
)
from utils import compute_hash

from fetchers.base import BaseFetcher, polite_sleep

_AUTH_URL = (
    "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    "?realm=/partenaire"
)
_SEARCH_URL = (
    "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
)

# Department codes for target locations
_DEPT_SEARCHES = [
    ("13", "Bouches-du-Rhône"),  # Marseille, Aix, Aubagne
    ("75", "Paris"),
    ("69", "Rhône"),             # Lyon
    ("34", "Hérault"),           # Montpellier
    ("06", "Alpes-Maritimes"),   # Nice
]

# ROME codes for broad coverage without keywords
_ROME_CODES = [
    ("M1805", "Études et développement informatique"),
    ("M1810", "Production et exploitation de systèmes d'information"),
    ("M1403", "Études et prospectives socio-économiques"),
]


class FranceTravailFetcher(BaseFetcher):
    """Fetch offers via the official France Travail REST API."""

    def __init__(self) -> None:
        super().__init__("FranceTravail")
        self._token: str | None = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
    )
    def _authenticate(self) -> str:
        """Obtain an OAuth2 bearer token."""
        resp = requests.post(
            _AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": FRANCE_TRAVAIL_CLIENT_ID,
                "client_secret": FRANCE_TRAVAIL_CLIENT_SECRET,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        token: str = resp.json()["access_token"]
        self.logger.info("Authenticated with France Travail API")
        return token

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
    )
    def _search(self, keyword: str, dept_code: str) -> list[dict[str, Any]]:
        """Run a single keyword + department search and return raw results."""
        if self._token is None:
            self._token = self._authenticate()

        params: dict[str, str] = {
            "motsCles": keyword,
            "departement": dept_code,
            "typeContrat": "CDI",
            "range": "0-149",
        }

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

        resp = requests.get(
            _SEARCH_URL, params=params, headers=headers, timeout=20,
        )

        if resp.status_code == 401:
            self.logger.warning("Token expired — re-authenticating")
            self._token = self._authenticate()
            headers["Authorization"] = f"Bearer {self._token}"
            resp = requests.get(
                _SEARCH_URL, params=params, headers=headers, timeout=20,
            )

        if resp.status_code == 204:
            return []

        resp.raise_for_status()
        data = resp.json()
        return data.get("resultats", [])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
    )
    def _search_by_rome(self, rome_code: str, dept_code: str) -> list[dict[str, Any]]:
        """Run a ROME code + department search and return raw results."""
        if self._token is None:
            self._token = self._authenticate()

        params: dict[str, str] = {
            "codeROME": rome_code,
            "departement": dept_code,
            "typeContrat": "CDI",
            "range": "0-149",
        }

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

        resp = requests.get(
            _SEARCH_URL, params=params, headers=headers, timeout=20,
        )

        if resp.status_code == 401:
            self.logger.warning("Token expired — re-authenticating")
            self._token = self._authenticate()
            headers["Authorization"] = f"Bearer {self._token}"
            resp = requests.get(
                _SEARCH_URL, params=params, headers=headers, timeout=20,
            )

        if resp.status_code == 204:
            return []

        resp.raise_for_status()
        data = resp.json()
        return data.get("resultats", [])

    @staticmethod
    def _clean_location(raw_location: str) -> str:
        """Clean France Travail location format. '13 - MARIGNANE' -> 'Marignane'."""
        cleaned = re.sub(r'^\d+\s*-\s*', '', raw_location)
        cleaned = re.sub(r'\s*\(Dept\.\)\s*$', '', cleaned)
        return cleaned.strip().title()

    @staticmethod
    def _map_offer(raw: dict[str, Any]) -> JobOffer:
        """Convert a raw API dict into a JobOffer."""
        title = raw.get("intitule", "")
        company = raw.get("entreprise", {}).get("nom", "N/A")
        location = FranceTravailFetcher._clean_location(
            raw.get("lieuTravail", {}).get("libelle", "")
        )
        contract_type = raw.get("typeContrat", "")
        description = raw.get("description", "")
        url = raw.get("origineOffre", {}).get("urlOrigine", "")
        if not url:
            offer_id = raw.get("id", "")
            url = f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}"
        date_posted = raw.get("dateCreation", "")
        experience = raw.get("experienceLibelle", "")
        salary_raw = raw.get("salaire", {})
        salary = salary_raw.get("libelle", "") if isinstance(salary_raw, dict) else ""

        return JobOffer(
            id=str(uuid.uuid4()),
            title=title,
            company=company,
            location=location,
            contract_type=contract_type,
            description=description,
            url=url,
            date_posted=date_posted,
            source="FranceTravail",
            experience_level=experience,
            salary=salary,
            hash=compute_hash(title, company, location),
        )

    def _collect_results(
        self,
        results: list[dict[str, Any]],
        seen_hashes: set[str],
        offers: list[JobOffer],
    ) -> None:
        """De-duplicate and append mapped offers."""
        for raw in results:
            offer = self._map_offer(raw)
            if offer.hash not in seen_hashes:
                seen_hashes.add(offer.hash)
                offers.append(offer)

    def fetch(self) -> list[JobOffer]:
        """Fetch job offers from France Travail using ROME codes then keywords."""
        seen_hashes: set[str] = set()
        offers: list[JobOffer] = []

        for rome_code, rome_label in _ROME_CODES:
            for dept_code, dept_name in _DEPT_SEARCHES:
                try:
                    self.logger.info(
                        "ROME search: %s (%s) in %s (%s)",
                        rome_label, rome_code, dept_name, dept_code,
                    )
                    results = self._search_by_rome(rome_code, dept_code)
                    self._collect_results(results, seen_hashes, offers)
                    polite_sleep(1.0, 2.0)
                except Exception:
                    self.logger.exception(
                        "Error ROME search %s in %s", rome_code, dept_name,
                    )

        for kw in self._build_search_queries():
            for dept_code, dept_name in _DEPT_SEARCHES:
                try:
                    self.logger.info("Keyword search: '%s' in %s (%s)", kw, dept_name, dept_code)
                    results = self._search(kw, dept_code)
                    self._collect_results(results, seen_hashes, offers)
                    polite_sleep(1.0, 2.0)
                except Exception:
                    self.logger.exception(
                        "Error searching '%s' in %s", kw, dept_name,
                    )

        self.logger.info(
            "FranceTravail: collected %d unique offers", len(offers),
        )
        return offers
