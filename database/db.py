"""
SQLite database manager for persisting and querying job offers.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Self

from config import JobOffer


class Database:
    """Thin wrapper around SQLite for the jobs table.

    Supports the context-manager protocol so it can be used with ``with``.
    """

    _CREATE_TABLE = """
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
            created_at      TEXT
        )
    """

    def __init__(self, db_path: str = "data/jobs.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(self._CREATE_TABLE)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Add new columns if they don't already exist (safe to run repeatedly)."""
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
        self._conn.execute(
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
        self._conn.commit()
        return True

    def job_exists(self, hash_value: str) -> bool:
        """Check whether a job with the given hash is already stored."""
        row = self._conn.execute(
            "SELECT 1 FROM jobs WHERE hash = ?", (hash_value,)
        ).fetchone()
        return row is not None

    def mark_sent(self, job_id: str) -> None:
        """Flag a job as sent to the notification channel."""
        self._conn.execute("UPDATE jobs SET sent = 1 WHERE id = ?", (job_id,))
        self._conn.commit()

    def get_unsent_jobs(self, min_score: int) -> list[JobOffer]:
        """Return unsent jobs whose score meets the threshold."""
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE sent = 0 AND score >= ? ORDER BY score DESC",
            (min_score,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_all_jobs(self, limit: int = 100) -> list[dict]:
        """Return the most recent jobs as plain dicts."""
        rows = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_favorited(self, job_id: str) -> None:
        """Mark a job as favorited."""
        self._conn.execute("UPDATE jobs SET favorited = 1 WHERE id = ?", (job_id,))
        self._conn.commit()

    def mark_ignored(self, job_id: str) -> None:
        """Mark a job as ignored."""
        self._conn.execute("UPDATE jobs SET ignored = 1 WHERE id = ?", (job_id,))
        self._conn.commit()

    def get_today_stats(self) -> dict:
        """Return stats for today's pipeline runs."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._conn.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN sent = 1 THEN 1 ELSE 0 END) as sent, "
            "MAX(score) as best_score "
            "FROM jobs WHERE created_at LIKE ?",
            (f"{today}%",),
        ).fetchone()
        return {
            "total_fetched": row["total"] or 0,
            "sent": row["sent"] or 0,
            "best_score": row["best_score"] or 0,
        }

    def get_top_jobs(self, n: int = 5, date: str | None = None) -> list[JobOffer]:
        """Return top N jobs by score, optionally filtered by date."""
        if date:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE created_at LIKE ? AND ignored = 0 "
                "ORDER BY score DESC LIMIT ?",
                (f"{date}%", n),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE ignored = 0 ORDER BY score DESC LIMIT ?",
                (n,),
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def search_jobs(self, keyword: str, limit: int = 10) -> list[JobOffer]:
        """Search jobs by keyword in title, company, or description."""
        pattern = f"%{keyword}%"
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE (title LIKE ? OR company LIKE ? OR description LIKE ?) "
            "AND ignored = 0 ORDER BY score DESC LIMIT ?",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_jobs_by_min_score(self, min_score: int, limit: int = 15) -> list[JobOffer]:
        """Return jobs with score >= min_score, sorted by score desc."""
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE score >= ? AND ignored = 0 "
            "ORDER BY score DESC LIMIT ?",
            (min_score, limit),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def count_jobs_by_min_score(self, min_score: int) -> int:
        """Count jobs with score >= min_score (excluding ignored)."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM jobs WHERE score >= ? AND ignored = 0",
            (min_score,),
        ).fetchone()
        return row["cnt"] or 0

    def get_recent_sent(self, limit: int = 10) -> list[JobOffer]:
        """Return the most recently sent jobs."""
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE sent = 1 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_favorites(self, limit: int = 20) -> list[JobOffer]:
        """Return favorited jobs."""
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE favorited = 1 ORDER BY score DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> JobOffer:
        d = dict(row)
        return JobOffer(
            id=d["id"],
            title=d["title"],
            company=d["company"],
            location=d["location"],
            contract_type=d["contract_type"],
            description=d["description"],
            url=d["url"],
            date_posted=d["date_posted"],
            source=d["source"],
            experience_level=d["experience_level"],
            remote_type=d["remote_type"],
            salary=d["salary"],
            hash=d["hash"],
            score=d["score"],
            favorited=d.get("favorited", 0),
            ignored=d.get("ignored", 0),
        )
