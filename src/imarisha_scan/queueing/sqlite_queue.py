from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4


@dataclass(slots=True)
class QueueJob:
    id: str
    source_path: str
    status: str
    created_at: datetime
    updated_at: datetime
    attempt_count: int
    lease_until: datetime | None = None
    last_error: str | None = None


class QueueStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    lease_until TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
                """
            )

    def enqueue(self, source_path: str) -> str:
        now = datetime.now(UTC).isoformat()
        job_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs(id, source_path, status, created_at, updated_at)
                VALUES(?, ?, 'queued', ?, ?)
                """,
                (job_id, source_path, now, now),
            )
        return job_id

    def claim_next(self, worker: str, lease_seconds: int = 300) -> QueueJob | None:
        del worker  # reserved for future worker ownership tracking
        self.requeue_expired_leases()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None

            now = datetime.now(UTC)
            lease_until = now + timedelta(seconds=lease_seconds)
            conn.execute(
                """
                UPDATE jobs
                SET status='processing',
                    updated_at=?,
                    lease_until=?,
                    attempt_count=attempt_count+1
                WHERE id=?
                """,
                (now.isoformat(), lease_until.isoformat(), row["id"]),
            )
            updated = conn.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
            return self._row_to_job(updated)

    def mark_done(self, job_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='done', updated_at=?, lease_until=NULL, last_error=NULL WHERE id=?",
                (now, job_id),
            )

    def mark_failed(self, job_id: str, error: str, requeue: bool = True) -> None:
        now = datetime.now(UTC).isoformat()
        status = "queued" if requeue else "failed"
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status=?, updated_at=?, lease_until=NULL, last_error=? WHERE id=?",
                (status, now, error, job_id),
            )

    def requeue_expired_leases(self) -> int:
        now_iso = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status='queued', lease_until=NULL, updated_at=?
                WHERE status='processing' AND lease_until IS NOT NULL AND lease_until < ?
                """,
                (now_iso, now_iso),
            )
            return cur.rowcount

    def get(self, job_id: str) -> QueueJob | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return None if row is None else self._row_to_job(row)

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> QueueJob:
        lease_until = datetime.fromisoformat(row["lease_until"]) if row["lease_until"] else None
        return QueueJob(
            id=row["id"],
            source_path=row["source_path"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            lease_until=lease_until,
            attempt_count=row["attempt_count"],
            last_error=row["last_error"],
        )
