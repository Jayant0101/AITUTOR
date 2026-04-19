from __future__ import annotations

import sqlite3
import os
import time
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class FileStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.database_url = os.getenv("DATABASE_URL")
        self.is_prod = (
            os.getenv("ENV", "").lower() == "production" 
            or os.getenv("RENDER") 
            or os.getenv("RAILWAY_ENVIRONMENT")
        )
        
        # Enforce PostgreSQL in Production (Phase 1)
        if self.is_prod:
            if not self.database_url:
                logger.critical("DATABASE_URL is missing in production environment!")
                raise RuntimeError("Production failure: DATABASE_URL must be set for PostgreSQL persistence.")
            if not self.database_url.startswith("postgresql"):
                logger.critical("DATABASE_URL must be a PostgreSQL connection string in production!")
                raise RuntimeError("Production failure: SQLite is not allowed in production.")

        self.is_postgres = self.database_url and self.database_url.startswith("postgresql")
        
        # Connection Pool (Phase 2 & 3)
        self._pg_pool = None
        if self.is_postgres:
            try:
                logger.info("Initializing PostgreSQL connection pool for FileStore...")
                self._pg_pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    dsn=self.database_url,
                    cursor_factory=RealDictCursor
                )
            except Exception as e:
                logger.error("Failed to initialize PG pool for FileStore. Ensure DATABASE_URL is correct.")
                if self.is_prod:
                    raise

    @contextmanager
    def _connect(self):
        start_time = time.time()
        connection = None
        
        try:
            if self.is_postgres:
                # Get connection from pool with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        connection = self._pg_pool.getconn()
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        logger.warning(f"FileStore DB connection attempt {attempt+1} failed, retrying...")
                        time.sleep(1)
                
                yield connection
                connection.commit()
            else:
                connection = sqlite3.connect(self.db_path)
                connection.row_factory = sqlite3.Row
                yield connection
                connection.commit()
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"FileStore database error: {e}", exc_info=True)
            raise
        finally:
            if connection:
                if self.is_postgres:
                    self._pg_pool.putconn(connection)
                else:
                    connection.close()
            
            # Slow query logging
            duration = time.time() - start_time
            if duration > 0.5:
                logger.warning(f"Slow FileStore database operation: {duration:.2f}s")

    def initialize(self) -> None:
        with self._connect() as conn:
            if self.is_postgres:
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS uploaded_files (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        content_type TEXT,
                        size BIGINT NOT NULL,
                        path TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            else:
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
            if self.is_postgres:
                conn.cursor().execute(
                    """
                    INSERT INTO uploaded_files (id, name, content_type, size, path, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
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
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO uploaded_files (id, name, content_type, size, path, created_at)
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
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute("SELECT id, name, content_type, size, path, created_at FROM uploaded_files WHERE id = %s", (file_id,))
                row = cur.fetchone()
            else:
                row = conn.execute(
                    "SELECT id, name, content_type, size, path, created_at FROM uploaded_files WHERE id = ?",
                    (file_id,),
                ).fetchone()
        return dict(row) if row else None
