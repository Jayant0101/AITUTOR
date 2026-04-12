from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime


class FileStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    content_type TEXT,
                    size INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_file(
        self, file_id: str, name: str, content_type: str, size: int, path: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO uploaded_files (id, name, content_type, size, path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    name,
                    content_type,
                    int(size),
                    path,
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get_file(self, file_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM uploaded_files WHERE id = ?",
                (file_id,),
            ).fetchone()
        return dict(row) if row else None
