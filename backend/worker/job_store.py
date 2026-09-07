# Duplicated from backend/api/job_store.py -- the API and worker are
# separate deployable processes and don't share a package yet. If this
# drifts out of sync, that's the sign to extract a shared library.
import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator


class JobStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    tickers TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    result TEXT,
                    created_at REAL NOT NULL
                )
                """
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def create_job(self, job_id: str, tickers: list[str]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (job_id, tickers, status, created_at)
                VALUES (?, ?, 'queued', ?)
                """,
                (job_id, json.dumps(tickers), time.time()),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT job_id, tickers, status, result FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "job_id": row["job_id"],
            "tickers": json.loads(row["tickers"]),
            "status": row["status"],
            "result": json.loads(row["result"]) if row["result"] else None,
        }

    def claim_next_job(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT job_id, tickers
                FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at, rowid
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                connection.execute("COMMIT")
                return None

            connection.execute(
                "UPDATE jobs SET status = 'running' WHERE job_id = ?",
                (row["job_id"],),
            )
            connection.execute("COMMIT")

        return {
            "job_id": row["job_id"],
            "tickers": json.loads(row["tickers"]),
        }

    def complete_job(self, job_id: str, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'done', result = ? WHERE job_id = ?",
                (json.dumps(result), job_id),
            )
