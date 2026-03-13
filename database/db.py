"""
Database manager for persisting and querying job offers.
Supports SQLite (local) and PostgreSQL (Railway/production).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Self

from config import JobOffer

DATABASE_URL = os.getenv("DATABASE_URL")


class Database:
    """Database wrapper supporting both SQLite and PostgreSQL.

    Automatically uses PostgreSQL if DATABASE_URL is set, otherwise SQLite.
    """

    _CREATE_TABLE_SQLITE = """
        CREATE TABLE IF NOT EXISTS jobs (
            id              TEXT PRIMARY KEY,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            contract_type   TEXT,
            experience_level TEXT,
            description     TEXT,
            url             TEXT,
            date_posted     TEXT,
            source          TEXT,
            remote_type     TEXT,
            salary          TEXT,
            score           INTEGER,
            hash            TEXT UNIQUE,
            sent            INTEGER DEFAULT 0,
            favorited       INTEGER DEFAULT 0,
            ignored         INTEGER DEFAULT 0,
            created_at      TEXT
        )
    """

    _CREATE_TABLE_PG = """
        CREATE TABLE IF NOT EXISTS jobs (
            id              TEXT PRIMARY KEY,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            contract_type   TEXT,
            experience_level TEXT,
            description     TEXT,
            url             TEXT,
            date_posted     TEXT,
            source          TEXT,
            remote_type     TEXT,
            salary          TEXT,
            score           INTEGER,
            hash            TEXT UNIQUE,
            sent            INTEGER DEFAULT 0,
            favorited       INTEGER DEFAULT 0,
            ignored         INTEGER DEFAULT 0,
            created_at      TEXT
        )
    """

    def __init__(self, db_path: str = "data/jobs.db") -> None:
        self._use_postgres = DATABASE_URL is not None
        
        if self._use_postgres:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self._conn = psycopg2.connect(DATABASE_URL)
            self._conn.autocommit = False
            self._cursor_factory = RealDictCursor
            self._conn.cursor().execute(self._CREATE_TABLE_PG)
            self._conn.commit()
        else:
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(self._CREATE_TABLE_SQLITE)
            self._conn.commit()
            self._migrate_sqlite()

    def _migrate_sqlite(self) -> None:
        """Add new columns if they don't already exist (SQLite only)."""
        migrations = [
            "ALTER TABLE jobs ADD COLUMN favorited INTEGER DEFAULT 0",
            "ALTER TABLE jobs ADD COLUMN ignored INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass
        self._conn.commit()

    def _execute(self, query: str, params: tuple = ()) -> Any:
        """Execute a query, handling differences between SQLite and PostgreSQL."""
        if self._use_postgres:
            pg_query = query.replace("?", "%s")
            pg_query = pg_query.replace("LIKE ?", "ILIKE %s")
            cur = self._conn.cursor(cursor_factory=self._cursor_factory)
            cur.execute(pg_query, params)
            return cur
        else:
            return self._conn.execute(query, params)

    def _fetchone(self, query: str, params: tuple = ()) -> dict | None:
        """Fetch one row as dict."""
        cur = self._execute(query, params)
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    def _fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        """Fetch all rows as list of dicts."""
        cur = self._execute(query, params)
        return [dict(r) for r in cur.fetchall()]

    def _commit(self) -> None:
        """Commit the transaction."""
        self._conn.commit()

    # -- context manager ----------------------------------------------------

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    # -- public API ---------------------------------------------------------

    def insert_job(self, job: JobOffer) -> bool:
        """Insert a job offer. Returns *False* if the hash already exists."""
        if self.job_exists(job.hash):
            return False
        self._execute(
            """
            INSERT INTO jobs
                (id, title, company, location, contract_type, experience_level,
                 description, url, date_posted, source, remote_type, salary,
                 score, hash, sent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                job.id,
                job.title,
                job.company,
                job.location,
                job.contract_type,
                job.experience_level,
                job.description,
                job.url,
                job.date_posted,
                job.source,
                job.remote_type,
                job.salary,
                job.score,
                job.hash,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._commit()
        return True

    def job_exists(self, hash_value: str) -> bool:
        """Check whether a job with the given hash is already stored."""
        row = self._fetchone("SELECT 1 FROM jobs WHERE hash = ?", (hash_value,))
        return row is not None

    def mark_sent(self, job_id: str) -> None:
        """Flag a job as sent to the notification channel."""
        self._execute("UPDATE jobs SET sent = 1 WHERE id = ?", (job_id,))
        self._commit()

    def get_unsent_jobs(self, min_score: int) -> list[JobOffer]:
        """Return unsent jobs whose score meets the threshold."""
        rows = self._fetchall(
            "SELECT * FROM jobs WHERE sent = 0 AND score >= ? ORDER BY score DESC",
            (min_score,),
        )
        return [self._row_to_job(r) for r in rows]

    def get_all_jobs(self, limit: int = 100) -> list[dict]:
        """Return the most recent jobs as plain dicts."""
        return self._fetchall(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        )

    def mark_favorited(self, job_id: str) -> None:
        """Mark a job as favorited."""
        self._execute("UPDATE jobs SET favorited = 1 WHERE id = ?", (job_id,))
        self._commit()

    def mark_ignored(self, job_id: str) -> None:
        """Mark a job as ignored."""
        self._execute("UPDATE jobs SET ignored = 1 WHERE id = ?", (job_id,))
        self._commit()

    def get_today_stats(self) -> dict:
        """Return stats for today's pipeline runs."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._fetchone(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN sent = 1 THEN 1 ELSE 0 END) as sent, "
            "MAX(score) as best_score "
            "FROM jobs WHERE created_at LIKE ?",
            (f"{today}%",),
        )
        return {
            "total_fetched": row["total"] or 0 if row else 0,
            "sent": row["sent"] or 0 if row else 0,
            "best_score": row["best_score"] or 0 if row else 0,
        }

    def get_top_jobs(self, n: int = 5, date: str | None = None) -> list[JobOffer]:
        """Return top N jobs by score, optionally filtered by date."""
        if date:
            rows = self._fetchall(
                "SELECT * FROM jobs WHERE created_at LIKE ? AND ignored = 0 "
                "ORDER BY score DESC LIMIT ?",
                (f"{date}%", n),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM jobs WHERE ignored = 0 ORDER BY score DESC LIMIT ?",
                (n,),
            )
        return [self._row_to_job(r) for r in rows]

    def search_jobs(self, keyword: str, limit: int = 10) -> list[JobOffer]:
        """Search jobs by keyword in title, company, or description."""
        pattern = f"%{keyword}%"
        rows = self._fetchall(
            "SELECT * FROM jobs WHERE (title LIKE ? OR company LIKE ? OR description LIKE ?) "
            "AND ignored = 0 ORDER BY score DESC LIMIT ?",
            (pattern, pattern, pattern, limit),
        )
        return [self._row_to_job(r) for r in rows]

    def get_jobs_by_min_score(self, min_score: int, limit: int = 15) -> list[JobOffer]:
        """Return jobs with score >= min_score, sorted by score desc."""
        rows = self._fetchall(
            "SELECT * FROM jobs WHERE score >= ? AND ignored = 0 "
            "ORDER BY score DESC LIMIT ?",
            (min_score, limit),
        )
        return [self._row_to_job(r) for r in rows]

    def count_jobs_by_min_score(self, min_score: int) -> int:
        """Count jobs with score >= min_score (excluding ignored)."""
        row = self._fetchone(
            "SELECT COUNT(*) as cnt FROM jobs WHERE score >= ? AND ignored = 0",
            (min_score,),
        )
        return row["cnt"] or 0 if row else 0

    def get_recent_sent(self, limit: int = 10) -> list[JobOffer]:
        """Return the most recently sent jobs."""
        rows = self._fetchall(
            "SELECT * FROM jobs WHERE sent = 1 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_job(r) for r in rows]

    def get_favorites(self, limit: int = 20) -> list[JobOffer]:
        """Return favorited jobs."""
        rows = self._fetchall(
            "SELECT * FROM jobs WHERE favorited = 1 ORDER BY score DESC LIMIT ?",
            (limit,),
        )
        return [self._row_to_job(r) for r in rows]

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _row_to_job(row: dict) -> JobOffer:
        return JobOffer(
            id=row["id"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            contract_type=row["contract_type"],
            description=row["description"],
            url=row["url"],
            date_posted=row["date_posted"],
            source=row["source"],
            experience_level=row["experience_level"],
            remote_type=row["remote_type"],
            salary=row["salary"],
            hash=row["hash"],
            score=row["score"],
            favorited=row.get("favorited", 0),
            ignored=row.get("ignored", 0),
        )
