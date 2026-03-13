"""Pre-scoring filters that discard obviously irrelevant offers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import MAX_OFFER_AGE_DAYS, PROFILE, JobOffer
from utils import normalize, setup_logger

logger = setup_logger(__name__)


def filter_by_contract(jobs: list[JobOffer]) -> list[JobOffer]:
    """Remove offers whose contract type, title, or description matches exclusions."""
    excluded = [normalize(c) for c in PROFILE["excluded_contracts"]]
    result: list[JobOffer] = []
    for job in jobs:
        ct = normalize(job.contract_type)
        title = normalize(job.title)
        if any(kw in ct for kw in excluded):
            continue
        if any(kw in title for kw in excluded):
            continue
        result.append(job)
    return result


def filter_by_experience(jobs: list[JobOffer]) -> list[JobOffer]:
    """Remove offers whose title contains senior/lead keywords."""
    excluded_kw = [normalize(k) for k in PROFILE["excluded_title_keywords"]]
    result: list[JobOffer] = []
    for job in jobs:
        title = normalize(job.title)
        if not any(kw in title for kw in excluded_kw):
            result.append(job)
    return result


def filter_by_location(jobs: list[JobOffer]) -> list[JobOffer]:
    """Keep offers in allowed cities, flagged remote, or with unknown location."""
    allowed = [normalize(c) for c in PROFILE["locations"]["paca"]]
    allowed += [normalize(c) for c in PROFILE["locations"]["other"]]

    result: list[JobOffer] = []
    for job in jobs:
        loc = normalize(job.location)
        remote = normalize(job.remote_type)

        if not loc:
            result.append(job)
            continue

        is_known = any(city in loc for city in allowed)
        is_remote = PROFILE.get("remote_accepted") and any(
            tag in remote or tag in loc
            for tag in ("remote", "teletravail", "full remote")
        )

        if is_known or is_remote:
            result.append(job)

    return result


def filter_by_date(jobs: list[JobOffer]) -> list[JobOffer]:
    """Keep offers posted within the last *MAX_OFFER_AGE_DAYS* days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_OFFER_AGE_DAYS)
    result: list[JobOffer] = []
    for job in jobs:
        if not job.date_posted:
            result.append(job)
            continue
        try:
            posted = datetime.fromisoformat(job.date_posted)
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            if posted >= cutoff:
                result.append(job)
        except (ValueError, TypeError):
            result.append(job)
    return result


def filter_offers(jobs: list[JobOffer]) -> list[JobOffer]:
    """Apply all filters in sequence and return surviving offers."""
    initial = len(jobs)
    jobs = filter_by_contract(jobs)
    logger.debug("After contract filter: %d/%d", len(jobs), initial)
    jobs = filter_by_experience(jobs)
    logger.debug("After experience filter: %d/%d", len(jobs), initial)
    jobs = filter_by_location(jobs)
    logger.debug("After location filter: %d/%d", len(jobs), initial)
    jobs = filter_by_date(jobs)
    logger.debug("After date filter: %d/%d", len(jobs), initial)
    return jobs
