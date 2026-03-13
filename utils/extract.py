"""Text extraction helpers — tech detection and description snippets."""

from __future__ import annotations

import re

from config import PROFILE

_GENERIC_TERMS = {"data", "backend", "api", "analytics"}

_CATEGORY_PRIORITY = ["backend", "frontend", "data", "api_archi", "ai"]


def _build_pattern(skill: str) -> re.Pattern[str]:
    """Build a regex pattern for a skill, handling special characters."""
    low = skill.lower()
    if low in _GENERIC_TERMS:
        return re.compile(r"(?!)")  # never matches
    if skill in ("C#",):
        return re.compile(re.escape(skill), re.IGNORECASE)
    if skill.startswith("."):
        return re.compile(re.escape(skill), re.IGNORECASE)
    escaped = re.escape(skill)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def extract_techs(description: str) -> list[str]:
    """Return up to 8 techs detected in *description*, deduplicated.

    Scans all skill categories from ``PROFILE["skills"]`` using word-boundary
    matching.  Results are ordered by category priority
    (backend > frontend > data > api_archi > ai) then by position within each
    category list.
    """
    if not description:
        return []

    seen: set[str] = set()
    result: list[str] = []

    for category in _CATEGORY_PRIORITY:
        skills = PROFILE["skills"].get(category, [])
        for skill in skills:
            if skill.lower() in _GENERIC_TERMS:
                continue
            pat = _build_pattern(skill)
            if pat.search(description):
                key = skill.lower()
                if key not in seen:
                    seen.add(key)
                    result.append(skill)
                    if len(result) >= 8:
                        return result

    return result


_SKIP_PREFIXES = (
    "nous recherchons",
    "dans le cadre de",
    "au sein de",
    "l'entreprise",
    "l'entreprise",
    "rejoignez",
)


def extract_snippet(description: str, max_len: int = 150) -> str:
    """Return a short, relevant snippet from *description*.

    Skips common intro phrases and picks the first sentence that looks like
    an actual task or tech mention.  Truncates at a word boundary.
    """
    if not description:
        return ""

    text = re.sub(r"\s+", " ", description).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)

    for sent in sentences:
        if any(sent.lower().startswith(p) for p in _SKIP_PREFIXES):
            continue
        snippet = sent.strip()
        if not snippet:
            continue
        if len(snippet) <= max_len:
            return snippet
        cut = snippet[:max_len].rsplit(" ", 1)[0]
        return cut + "..."

    fallback = text[:max_len].rsplit(" ", 1)[0]
    return fallback + "..." if len(text) > max_len else text
