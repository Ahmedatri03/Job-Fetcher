"""
Configuration module — single source of truth for all settings and matching criteria.

Loads environment variables from .env and exposes them as module-level constants.
Defines the candidate PROFILE dict used by the scoring engine.
Defines the JobOffer dataclass shared across all modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent / ".env")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
FRANCE_TRAVAIL_CLIENT_ID: str = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "")
FRANCE_TRAVAIL_CLIENT_SECRET: str = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "")
SCORE_THRESHOLD: int = int(os.getenv("SCORE_THRESHOLD", "50"))
FETCH_INTERVAL_HOURS: int = int(os.getenv("FETCH_INTERVAL_HOURS", "1"))
MAX_OFFER_AGE_DAYS: int = int(os.getenv("MAX_OFFER_AGE_DAYS", "15"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Candidate profile — used by the scoring engine
# ---------------------------------------------------------------------------

PROFILE: dict = {
    "target_titles": [
        "développeur",
        "développeur logiciel",
        "développeur backend",
        "développeur full stack",
        "ingénieur logiciel",
        "software engineer",
        "développeur C#",
        "développeur .NET",
        "développeur Python",
        "développeur Node",
        "développeur JavaScript",
        "développeur TypeScript",
        "développeur web",
        "développeur mobile",
        "data analyst",
        "analyste BI",
        "data engineer",
        "ingénieur data",
    ],
    "skills": {
        "backend": ["C#", ".NET", "Node.js", "Python", "Django", "Supabase"],
        "frontend": ["React", "React Native", "TypeScript", "JavaScript", "Expo"],
        "api_archi": ["API", "REST", "microservices", "backend", "JWT", "RabbitMQ"],
        "data": ["SQL", "Power BI", "DAX", "data", "analytics", "MongoDB", "PostgreSQL"],
        "ai": ["OpenAI", "LLM", "IA", "machine learning", "NLP"],
    },
    "junior_keywords": [
        "junior",
        "0-2 ans",
        "0 à 2 ans",
        "1-2 ans",
        "1 à 3 ans",
        "jeune diplômé",
        "débutant",
        "première expérience",
        "entry level",
    ],
    "excluded_contracts": [
        "alternance",
        "apprentissage",
        "stage",
        "internship",
        "freelance",
        "indépendant",
        "CDD",
        "intérim",
    ],
    "excluded_title_keywords": [
        "senior",
        "lead",
        "manager",
        "principal",
        "directeur",
        "head of",
    ],
    "penalty_keywords": {
        -20: ["confirmé", "expérimenté"],
        -30: ["5 ans d'expérience", "7 ans", "10 ans"],
    },
    "locations": {
        "paca": [
            "Marseille",
            "Aix-en-Provence",
            "Aubagne",
            "La Ciotat",
            "Vitrolles",
            "Marignane",
            "Martigues",
            "Gardanne",
            "Salon-de-Provence",
        ],
        "other": [
            "Paris",
            "Île-de-France",
            "Lyon",
            "Montpellier",
            "Nice",
        ],
    },
    "remote_accepted": True,
}

# ---------------------------------------------------------------------------
# Shared data model
# ---------------------------------------------------------------------------


@dataclass
class JobOffer:
    """Represents a single job offer collected from any source."""

    id: str
    title: str
    company: str
    location: str
    contract_type: str
    description: str
    url: str
    date_posted: str
    source: str
    experience_level: str = ""
    remote_type: str = ""
    salary: str = ""
    hash: str = ""
    score: int = 0
    favorited: int = 0
    ignored: int = 0
