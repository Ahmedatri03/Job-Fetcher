"""fetchers — pluggable job-offer collectors."""

from fetchers.apec import ApecFetcher
from fetchers.base import BaseFetcher
from fetchers.francetravail import FranceTravailFetcher
from fetchers.indeed import IndeedFetcher
from fetchers.linkedin import LinkedInFetcher
from fetchers.wttj import WTTJFetcher

__all__ = [
    "BaseFetcher",
    "FranceTravailFetcher",
    "IndeedFetcher",
    "WTTJFetcher",
    "ApecFetcher",
    "LinkedInFetcher",
]
