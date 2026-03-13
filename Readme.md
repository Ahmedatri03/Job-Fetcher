# Job Fetcher & CV Matching Tool

## 1. Objectif du projet

Construire un outil automatisé qui :

- Récupère des offres d'emploi depuis plusieurs sources (APIs + scraping)
- Filtre les offres selon des critères précis (contrat, expérience, localisation)
- Évalue la compatibilité avec le CV du candidat via un système de scoring
- Attribue un score de pertinence sur 100
- Envoie les meilleures offres sur Telegram

L'objectif est de détecter rapidement les offres de premier emploi en CDI compatibles avec le profil.
Le système fonctionne en continu et envoie uniquement les **nouvelles** offres pertinentes.

---

## 2. Profil candidat (utilisé pour scoring)

Le système doit matcher les offres avec ce profil.

### Identité

- **Nom** : Ahmed ELATRI
- **Titre** : Ingénieur Logiciel & Data / Développeur Full Stack (MIAGE)
- **Localisation** : Aix-en-Provence, France
- **Formation** : Master 2 MIAGE Ingénierie de données — Aix-Marseille Université (2025-2026)
- **Niveau** : Jeune diplômé / première expérience (apprentissage + stage)
- **Langues** : Français (courant), Anglais (C1 — TOEIC)

### Expérience

- **Apprenti Développeur Full Stack** — Arlux Lighting, Aubagne (Nov 2024 – Present)
  - API REST en C#/.NET interfacée avec Sage 100
  - Automatisation extraction/traitement données via Django
  - Dashboards Power BI pour pilotage métier

- **Développeur Logiciel — Stage** — FEL Mines Saint-Étienne, Gardanne (Avr 2024 – Août 2024)
  - Interface graphique en Python
  - Intégration dispositifs de mesure via Raspberry Pi

### Compétences techniques

| Catégorie | Technologies |
|---|---|
| **Langages** | TypeScript, JavaScript, C#, Python, SQL |
| **Backend** | .NET, Node.js, Supabase Edge Functions, Django |
| **Frontend** | React, React Native, Expo |
| **Bases de données** | PostgreSQL, MongoDB, SQL Server |
| **API & Intégration** | REST, JWT, RabbitMQ, intégration d'APIs tierces |
| **Data & BI** | Power BI, DAX, modélisation SQL |
| **Outils** | Git, Postman, Docker, Linux |
| **IA / LLM** | OpenAI API, agents IA, prompt engineering |

### Domaines de compétence

- Backend development & APIs
- Data / BI / Analytics
- Web & Mobile development
- Intégration systèmes
- IA / LLM

---

## 3. Zones géographiques ciblées

Le système filtre uniquement les offres situées dans ces zones :

### Région PACA (rayon 40 km autour d'Aix-en-Provence)

- Marseille
- Aix-en-Provence
- Aubagne
- La Ciotat
- Vitrolles
- Marignane
- Martigues
- Gardanne
- Salon-de-Provence

### Autres métropoles (rayon 20 km autour du centre)

- Paris / Île-de-France
- Lyon
- Montpellier
- Nice

### Remote

- Les offres **full remote** basées en France sont acceptées quelle que soit la localisation de l'entreprise.
- Les offres **hybride** sont acceptées si le site est dans une zone ci-dessus.

---

## 4. Type de contrat

**Autorisé** : CDI uniquement

**Exclusion dure** (filtrage avant scoring — offre rejetée immédiatement) :

- alternance
- apprentissage
- stage
- internship
- freelance / indépendant
- CDD
- intérim

> Ces offres ne passent jamais au scoring. Elles sont ignorées dès le filtrage.

---

## 5. Niveau d'expérience

**Inclure** :

- junior
- débutant
- jeune diplômé
- 0-2 ans / 0 à 2 ans / 1-2 ans / 1 à 3 ans
- première expérience
- entry level
- sans expérience requise

**Exclusion dure** (rejet immédiat si le titre contient) :

- senior
- lead
- manager
- principal
- directeur / head of

**Pénalité au scoring** (si détecté dans la description uniquement) :

- confirmé / expérimenté → pénalité -20
- 5+ ans / 7+ ans / 10+ ans d'expérience requis → pénalité -30

> Logique : un titre "Senior" est un rejet clair. Mais "confirmé" dans une description peut être ambigu, donc on pénalise au scoring plutôt que d'exclure.

---

## 6. Titres de postes ciblés

Inclure si le titre contient (insensible à la casse) :

- développeur / developpeur
- développeur logiciel
- développeur backend / développeur back-end
- développeur full stack / développeur fullstack
- développeur front-end / développeur frontend
- ingénieur logiciel / ingénieur développement
- software engineer / software developer
- développeur C# / développeur .NET
- développeur Python / développeur Node
- développeur JavaScript / développeur TypeScript
- développeur web
- développeur mobile
- data analyst / analyste BI
- data engineer
- ingénieur data

---

## 7. Sources d'offres d'emploi

### Priorité 1 — APIs officielles (fiables, stables)

| Source | Méthode | Notes |
|---|---|---|
| **France Travail** (ex-Pôle Emploi) | API REST officielle | Gratuite, bien documentée, filtres natifs (contrat, lieu, métier) |
| **Welcome to the Jungle** | API / scraping structuré | Offres tech de qualité |

### Priorité 2 — Scraping structuré

| Source | Méthode | Notes |
|---|---|---|
| **Indeed** | Scraping avec rotation user-agents | Anti-bot agressif, nécessite retry + headers rotatifs |
| **APEC** | Scraping / API | Offres cadre/dev, très pertinent pour profil MIAGE |

### Priorité 3 — Optionnel

| Source | Méthode | Notes |
|---|---|---|
| **LinkedIn** | Scraping pages publiques | Difficile (anti-bot), en dernier recours |
| **Greenhouse / Lever** | Scraping `company.greenhouse.io` | Nécessite une liste d'entreprises cibles. Non prioritaire. |

> **Note** : Toujours préférer les APIs aux scraping. Le scraping doit implémenter retry avec exponential backoff, rotation de User-Agent, et respecter un délai entre les requêtes.

---

## 8. Structure de données d'une offre

Chaque offre est normalisée dans ce format :

```python
@dataclass
class JobOffer:
    id: str
    title: str
    company: str
    location: str
    contract_type: str
    experience_level: str | None
    description: str
    url: str
    date_posted: str          # ISO 8601
    source: str               # "francetravail", "indeed", "wttj", etc.
    remote_type: str | None   # "remote", "hybrid", "onsite"
    salary: str | None        # Si disponible
    hash: str                 # hash(title + company + location)
    score: int | None
```

---

## 9. Filtrage par date

Le système ne traite que les offres publiées dans les **15 derniers jours**.

Les offres plus anciennes sont ignorées, même si elles n'ont jamais été vues.

---

## 10. Système de scoring

Chaque offre passant le filtrage reçoit un score sur **100**.

### Barème

| Critère | Condition | Points |
|---|---|---|
| **Titre** | Contient développeur / ingénieur logiciel / software engineer | **+25** |
| **Technologies backend** | Description contient : C#, .NET, Node.js, Python, Django, Supabase | **+20** |
| **Technologies frontend** | Description contient : React, React Native, TypeScript, JavaScript, Expo | **+10** |
| **API / Architecture** | Description contient : API, REST, microservices, backend, JWT, RabbitMQ | **+15** |
| **Profil junior** | Description contient : junior, 0-2 ans, jeune diplômé, débutant, première expérience | **+15** |
| **Data / BI** | Description contient : SQL, Power BI, DAX, data, analytics, MongoDB, PostgreSQL | **+10** |
| **IA / LLM** | Description contient : OpenAI, LLM, IA, machine learning, NLP | **+5** |
| **Total maximum** | | **100** |

### Pénalités (appliquées sur le score)

| Condition | Pénalité |
|---|---|
| Description contient "confirmé" / "expérimenté" | **-20** |
| Description exige 5+ ans / 7+ ans / 10+ ans | **-30** |

> **Note** : Les mots-clés sont matchés de façon insensible à la casse. Un même mot-clé dans une catégorie ne compte qu'une fois (pas de double comptage).

### Score minimum : un seul mot-clé par catégorie suffit à déclencher les points de cette catégorie.

---

## 11. Seuil de pertinence

Le système envoie une offre sur Telegram **seulement si score >= 50**.

---

## 12. Déduplication

Le système ne doit jamais envoyer deux fois la même offre.

**Méthode** :

```
hash = sha256(normalize(title) + normalize(company) + normalize(location))
```

- `normalize` : lowercase, strip whitespace, supprimer accents
- Stockage du hash en base de données
- Vérification avant chaque envoi

---

## 13. Base de données

**Moteur** : SQLite

**Table** : `jobs`

| Colonne | Type | Description |
|---|---|---|
| id | TEXT PRIMARY KEY | UUID |
| title | TEXT | Titre du poste |
| company | TEXT | Nom de l'entreprise |
| location | TEXT | Localisation |
| contract_type | TEXT | CDI |
| experience_level | TEXT | junior, etc. |
| description | TEXT | Description complète |
| url | TEXT | Lien vers l'offre |
| date_posted | TEXT | Date ISO 8601 |
| source | TEXT | Origine (francetravail, indeed...) |
| remote_type | TEXT | remote / hybrid / onsite |
| salary | TEXT | Salaire si dispo |
| score | INTEGER | Score de compatibilité |
| hash | TEXT UNIQUE | Hash de déduplication |
| sent | INTEGER DEFAULT 0 | 1 si envoyé sur Telegram |
| created_at | TEXT | Date d'insertion en base |

---

## 14. Notifications Telegram

Créer un **Telegram Bot** via @BotFather.

Format du message :

```
💼 Nouvelle offre pertinente

📋 Poste : Développeur Backend Junior
🏢 Entreprise : Capgemini
📍 Ville : Lyon
🏠 Mode : Hybride
💰 Salaire : 32-38K€

⭐ Score compatibilité : 72/100

🔗 Lien : https://...
📡 Source : France Travail
```

---

## 15. Fréquence d'exécution

Le fetch s'exécute **toutes les 3 heures**.

---

## 16. Stack technique

| Composant | Technologie |
|---|---|
| Langage | Python 3.11+ |
| HTTP | `requests` + `httpx` (async) |
| Scraping | `beautifulsoup4`, `lxml` |
| Base de données | `sqlite3` (stdlib) |
| Telegram | `python-telegram-bot` |
| Scheduler | `APScheduler` |
| Config / secrets | `python-dotenv` (fichier `.env`) |
| Retry | `tenacity` |
| Logging | `logging` (stdlib) |
| Hashing | `hashlib` (stdlib) |

---

## 17. Configuration & secrets

Tous les secrets et paramètres configurables sont dans un fichier **`.env`** (jamais commité) :

```env
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
FRANCE_TRAVAIL_CLIENT_ID=xxx
FRANCE_TRAVAIL_CLIENT_SECRET=xxx
SCORE_THRESHOLD=50
FETCH_INTERVAL_HOURS=3
MAX_OFFER_AGE_DAYS=15
LOG_LEVEL=INFO
```

Un fichier `.env.example` est fourni comme modèle.

---

## 18. Architecture du projet

```
job-fetcher/
│
├── main.py                  # Point d'entrée + scheduler
├── config.py                # Chargement .env + constantes
├── requirements.txt
├── .env.example
├── .gitignore
│
├── fetchers/
│   ├── __init__.py
│   ├── base.py              # Classe abstraite BaseFetcher
│   ├── francetravail.py     # API France Travail
│   ├── indeed.py            # Scraping Indeed
│   ├── wttj.py              # Welcome to the Jungle
│   ├── apec.py              # APEC
│   └── linkedin.py          # LinkedIn (optionnel)
│
├── scoring/
│   ├── __init__.py
│   ├── base.py              # Interface abstraite BaseScorer
│   ├── keyword_scorer.py    # Scoring par mots-clés (v1)
│   └── filters.py           # Filtres contrat / expérience / date / lieu
│
├── database/
│   ├── __init__.py
│   └── db.py                # CRUD SQLite
│
├── notifier/
│   ├── __init__.py
│   └── telegram.py          # Envoi Telegram
│
├── utils/
│   ├── __init__.py
│   ├── dedupe.py            # Hashing + déduplication
│   └── logger.py            # Configuration logging
│
└── tests/
    ├── test_scorer.py
    ├── test_filters.py
    └── test_dedupe.py
```

---

## 19. Workflow d'exécution

```
1. Fetch des offres (toutes sources en parallèle)
       ↓
2. Normalisation au format JobOffer
       ↓
3. Filtrage date (< 15 jours)
       ↓
4. Filtrage contrat (CDI uniquement — exclusion dure)
       ↓
5. Filtrage expérience titre (exclure senior/lead/manager)
       ↓
6. Déduplication (hash déjà en base ?)
       ↓
7. Scoring (mots-clés + pénalités)
       ↓
8. Stockage en base SQLite
       ↓
9. Notification Telegram si score >= 50
       ↓
10. Logging du résultat (nb offres traitées, envoyées, rejetées)
```

---

## 20. Logging

Le système utilise le module `logging` Python avec :

- **Console** : niveau INFO (résumé de chaque run)
- **Fichier** : `logs/job_fetcher.log` avec rotation (5 Mo max, 3 fichiers)
- Format : `[2026-03-05 14:30:00] [INFO] [francetravail] 23 offres récupérées, 8 après filtrage, 3 envoyées`

---

## 21. Gestion des erreurs & retry

- Chaque fetcher est wrappé dans un try/except — une source en erreur ne bloque pas les autres
- Retry avec **exponential backoff** (3 tentatives, délai 2s → 4s → 8s) via `tenacity`
- Rotation de User-Agent pour le scraping
- Timeout de 30s par requête
- Rate limiting : 1 requête/seconde minimum entre les pages d'une même source

---

## 22. Évolutions futures

Le projet est conçu pour permettre facilement :

### Matching IA (v2)

- Remplacement du `KeywordScorer` par un `EmbeddingScorer` (même interface `BaseScorer`)
- Comparaison CV ↔ description via embeddings (OpenAI / sentence-transformers)
- Le scoring par mots-clés reste en fallback

### Résumé IA des offres

- Génération d'un résumé expliquant pourquoi l'offre correspond au profil
- Intégré au message Telegram

### Dashboard

- Interface web simple (Streamlit ou FastAPI + React) pour visualiser les offres, les scores, et les statistiques

### Candidature semi-automatisée

- Génération de lettres de motivation adaptées via LLM
- Pré-remplissage de formulaires de candidature

---

## 23. Critères de qualité

Le code doit être :

- **Modulaire** : chaque composant est indépendant et testable
- **Typé** : type hints Python partout
- **Documenté** : docstrings sur les classes et fonctions publiques
- **Robuste** : gestion d'erreurs, retry, logging
- **Configurable** : tout paramètre modifiable via `.env`
- **Extensible** : ajout d'une source ou d'un scorer = une seule classe à créer

---

## 24. Résultat attendu

Le système fonctionne de façon **autonome**, tourne toutes les 3 heures, et envoie uniquement les meilleures offres correspondant au profil d'Ahmed ELATRI — développeur full stack junior, MIAGE, basé à Aix-en-Provence.
