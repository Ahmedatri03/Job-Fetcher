"""Tests for scoring.filters — pre-scoring offer filters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config import JobOffer
from scoring.filters import (
    filter_by_contract,
    filter_by_date,
    filter_by_experience,
    filter_by_location,
)


def _make_job(**overrides) -> JobOffer:
    defaults = {
        "id": "test-1",
        "title": "Développeur Backend",
        "company": "Acme",
        "location": "Marseille",
        "contract_type": "CDI",
        "description": "",
        "url": "https://example.com",
        "date_posted": datetime.now(timezone.utc).isoformat(),
        "source": "test",
    }
    defaults.update(overrides)
    return JobOffer(**defaults)


class TestFilterByContract:
    def test_removes_alternance(self) -> None:
        jobs = [_make_job(contract_type="Alternance"), _make_job(contract_type="CDI")]
        result = filter_by_contract(jobs)
        assert len(result) == 1
        assert result[0].contract_type == "CDI"

    def test_removes_stage(self) -> None:
        jobs = [_make_job(contract_type="Stage")]
        assert filter_by_contract(jobs) == []

    def test_keeps_cdi(self) -> None:
        jobs = [_make_job(contract_type="CDI")]
        assert len(filter_by_contract(jobs)) == 1


class TestFilterByExperience:
    def test_removes_senior_title(self) -> None:
        jobs = [_make_job(title="Senior Développeur Backend")]
        assert filter_by_experience(jobs) == []

    def test_removes_lead_title(self) -> None:
        jobs = [_make_job(title="Lead Developer Python")]
        assert filter_by_experience(jobs) == []

    def test_keeps_junior_title(self) -> None:
        jobs = [_make_job(title="Développeur Backend Junior")]
        assert len(filter_by_experience(jobs)) == 1


class TestFilterByLocation:
    def test_keeps_paca_cities(self) -> None:
        for city in ("Marseille", "Aix-en-Provence", "Aubagne"):
            jobs = [_make_job(location=city)]
            result = filter_by_location(jobs)
            assert len(result) == 1, f"{city} should be kept"

    def test_keeps_paris(self) -> None:
        jobs = [_make_job(location="Paris")]
        assert len(filter_by_location(jobs)) == 1

    def test_removes_unknown_city(self) -> None:
        jobs = [_make_job(location="Vladivostok")]
        assert filter_by_location(jobs) == []

    def test_keeps_remote(self) -> None:
        jobs = [_make_job(location="Anywhere", remote_type="Full remote")]
        assert len(filter_by_location(jobs)) == 1


class TestFilterByDate:
    def test_keeps_recent_jobs(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(days=2)
        jobs = [_make_job(date_posted=recent.isoformat())]
        assert len(filter_by_date(jobs)) == 1

    def test_removes_old_jobs(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=60)
        jobs = [_make_job(date_posted=old.isoformat())]
        assert filter_by_date(jobs) == []

    def test_keeps_jobs_without_date(self) -> None:
        jobs = [_make_job(date_posted="")]
        assert len(filter_by_date(jobs)) == 1
