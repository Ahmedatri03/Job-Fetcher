"""
Text normalisation and deduplication helpers.
"""

from __future__ import annotations

import hashlib
import unicodedata


def normalize(text: str) -> str:
    """Lowercase, strip, and remove accents from *text*."""
    text = text.strip().lower()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def compute_hash(title: str, company: str, location: str) -> str:
    """Return a SHA-256 hex digest for a normalised (title, company, location) triple."""
    combined = f"{normalize(title)}|{normalize(company)}|{normalize(location)}"
    return hashlib.sha256(combined.encode()).hexdigest()
