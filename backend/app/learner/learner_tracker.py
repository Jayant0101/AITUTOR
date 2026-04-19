from __future__ import annotations

import sqlite3
import os
import time
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


class LearnerTracker:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.database_url = os.getenv("DATABASE_URL")
        
        # If DATABASE_URL is provided it must be a valid PostgreSQL URL; if it is
        # absent the app falls back to SQLite so that a fresh Railway/Render deploy
        # works out-of-the-box without Supabase configured yet.
        if self.database_url and not self.database_url.startswith("postgresql"):
            logger.critical("DATABASE_URL is set but is not a PostgreSQL connection string!")
            raise RuntimeError("Configuration error: DATABASE_URL must be a postgresql:// URI.")

        self.is_postgres = self.database_url and self.database_url.startswith("postgresql")
        
        # Connection Pool (Phase 2 & 3)
        self._pg_pool = None
        if self.is_postgres:
            try:
                logger.info("Initializing PostgreSQL connection pool...")
                # Add retry on pool initialization
                for attempt in range(3):
                    try:
                        self._pg_pool = pool.ThreadedConnectionPool(
                            minconn=2,
                            maxconn=20,
                            dsn=self.database_url,
                            cursor_factory=RealDictCursor
                        )
                        logger.info("PG Pool initialized successfully.")
                        break
                    except Exception as e:
                        if attempt == 2:
                            # Don't log the full exception if it might contain the DSN
                            logger.error("Final PG Pool init attempt failed. Check environment configuration.")
                            raise
                        logger.warning(f"PG Pool init attempt {attempt+1} failed. Retrying...")
                        time.sleep(2)
            except Exception as e:
                logger.error(f"CRITICAL: Failed to initialize PG pool: {e}")
                raise RuntimeError(f"PostgreSQL connection pool failed to initialize: {e}") from e

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
                        logger.warning(f"DB connection attempt {attempt+1} failed, retrying...")
                        time.sleep(1)
                
                yield connection
                connection.commit()
            else:
                # SQLite fallback only for local dev
                connection = sqlite3.connect(self.db_path, timeout=30.0)
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA journal_mode=WAL")
                yield connection
                connection.commit()
        except Exception as e:
            if connection:
                if self.is_postgres:
                    connection.rollback()
                else:
                    connection.rollback()
            
            # Observability (Phase 3)
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            if connection:
                if self.is_postgres:
                    self._pg_pool.putconn(connection)
                else:
                    connection.close()
            
            # Observability: Slow Query Logging
            duration = time.time() - start_time
            if duration > 0.5: # 500ms threshold
                logger.warning(f"Slow database operation detected: {duration:.2f}s")

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            if self.is_postgres:
                # Postgres specific SERIAL and syntax
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE,
                        password_hash TEXT,
                        display_name TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS generated_quizzes (
                        quiz_id TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS nodes_mastery (
                        user_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        mastery REAL NOT NULL DEFAULT 0.25,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        correct_attempts INTEGER NOT NULL DEFAULT 0,
                        last_result INTEGER,
                        trend REAL NOT NULL DEFAULT 0.0,
                        last_review_at TEXT,
                        next_review_at TEXT,
                        last_interval_days INTEGER NOT NULL DEFAULT 1,
                        difficulty_bias REAL NOT NULL DEFAULT 1.0,
                        PRIMARY KEY (user_id, node_id),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS quiz_history (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        question TEXT,
                        expected_answer TEXT,
                        user_answer TEXT,
                        is_correct INTEGER NOT NULL,
                        difficulty TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS quiz_sessions (
                        id          SERIAL PRIMARY KEY,
                        user_id     TEXT NOT NULL,
                        topic       TEXT NOT NULL,
                        difficulty  TEXT NOT NULL DEFAULT 'medium',
                        num_questions INTEGER NOT NULL DEFAULT 0,
                        score       INTEGER NOT NULL DEFAULT 0,
                        total       INTEGER NOT NULL DEFAULT 0,
                        percentage  REAL NOT NULL DEFAULT 0.0,
                        time_taken  INTEGER NOT NULL DEFAULT 0,
                        feedback    TEXT,
                        taken_at    TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS learner_profile (
                        user_id         TEXT NOT NULL,
                        topic           TEXT NOT NULL,
                        mastery_score   REAL NOT NULL DEFAULT 0.0,
                        quizzes_taken   INTEGER NOT NULL DEFAULT 0,
                        avg_score       REAL NOT NULL DEFAULT 0.0,
                        last_updated    TEXT,
                        PRIMARY KEY (user_id, topic),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        feedback TEXT,
                        rating INTEGER,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                # Analytics Tables (Phase 2)
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_events (
                        id SERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata JSONB,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                conn.cursor().execute(
                    """
                    CREATE TABLE IF NOT EXISTS usage_metrics (
                        id SERIAL PRIMARY KEY,
                        metric_name TEXT NOT NULL,
                        value REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata JSONB
                    )
                    """
                )
            else:
                # SQLite schema (already exists in your file)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE,
                        password_hash TEXT,
                        display_name TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS generated_quizzes (
                        quiz_id TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                
                self._ensure_user_columns(conn)

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nodes_mastery (
                        user_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        mastery REAL NOT NULL DEFAULT 0.25,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        correct_attempts INTEGER NOT NULL DEFAULT 0,
                        last_result INTEGER,
                        trend REAL NOT NULL DEFAULT 0.0,
                        last_review_at TEXT,
                        next_review_at TEXT,
                        last_interval_days INTEGER NOT NULL DEFAULT 1,
                        difficulty_bias REAL NOT NULL DEFAULT 1.0,
                        PRIMARY KEY (user_id, node_id),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS quiz_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        question TEXT,
                        expected_answer TEXT,
                        user_answer TEXT,
                        is_correct INTEGER NOT NULL,
                        difficulty TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )

                # ── NEW TABLES ────────────────────────────────────────────────
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS quiz_sessions (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id     TEXT NOT NULL,
                        topic       TEXT NOT NULL,
                        difficulty  TEXT NOT NULL DEFAULT 'medium',
                        num_questions INTEGER NOT NULL DEFAULT 0,
                        score       INTEGER NOT NULL DEFAULT 0,
                        total       INTEGER NOT NULL DEFAULT 0,
                        percentage  REAL NOT NULL DEFAULT 0.0,
                        time_taken  INTEGER NOT NULL DEFAULT 0,
                        feedback    TEXT,
                        taken_at    TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS learner_profile (
                        user_id         TEXT NOT NULL,
                        topic           TEXT NOT NULL,
                        mastery_score   REAL NOT NULL DEFAULT 0.0,
                        quizzes_taken   INTEGER NOT NULL DEFAULT 0,
                        avg_score       REAL NOT NULL DEFAULT 0.0,
                        last_updated    TEXT,
                        PRIMARY KEY (user_id, topic),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        feedback TEXT,
                        rating INTEGER,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                # Analytics Tables (Phase 2 - SQLite fallback)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usage_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        metric_name TEXT NOT NULL,
                        value REAL NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata TEXT
                    )
                    """
                )

    def _ensure_user_columns(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        if "display_name" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
        if "email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

    def ensure_user(self, user_id: str, display_name: str | None = None) -> None:
        with self._connect() as conn:
            if self.is_postgres:
                conn.cursor().execute(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, created_at)
                    VALUES (%s, NULL, NULL, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        user_id,
                        display_name or user_id,
                        datetime.now(UTC).isoformat(),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (id, email, password_hash, display_name, created_at)
                    VALUES (?, NULL, NULL, ?, ?)
                    """,
                    (
                        user_id,
                        display_name or user_id,
                        datetime.now(UTC).isoformat(),
                    ),
                )

    def register_user(
        self, user_id: str, email: str, password_hash: str, display_name: str = ""
    ) -> dict:
        """Register a new user with email and hashed password."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            if self.is_postgres:
                conn.cursor().execute(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, email, password_hash, display_name or email, now),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash, display_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, email, password_hash, display_name or email, now),
                )
        return {
            "user_id": user_id,
            "email": email,
            "display_name": display_name or email,
            "created_at": now,
        }

    def get_user_by_email(self, email: str) -> dict | None:
        """Look up user by email. Returns dict or None."""
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                row = cur.fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM users WHERE email = ?", (email,)
                ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Look up user by id. Returns dict or None."""
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ).fetchone()
        return dict(row) if row else None

    def get_mastery_by_node(self, user_id: str, node_ids: list[str]) -> dict[str, dict]:
        if not node_ids:
            return {}

        if self.is_postgres:
            placeholders = ",".join(["%s"] * len(node_ids))
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"""
                    SELECT *
                    FROM nodes_mastery
                    WHERE user_id = %s AND node_id IN ({placeholders})
                    """,
                    [user_id, *node_ids],
                )
                rows = cur.fetchall()
        else:
            placeholders = ",".join(["?"] * len(node_ids))
            with self._connect() as conn:
                rows = conn.execute(
                    f"""
                    SELECT *
                    FROM nodes_mastery
                    WHERE user_id = ? AND node_id IN ({placeholders})
                    """,
                    [user_id, *node_ids],
                ).fetchall()

        existing = {row["node_id"]: dict(row) for row in rows}
        output: dict[str, dict] = {}
        for node_id in node_ids:
            output[node_id] = existing.get(
                node_id,
                {
                    "user_id": user_id,
                    "node_id": node_id,
                    "mastery": 0.25,
                    "attempts": 0,
                    "correct_attempts": 0,
                    "last_result": None,
                    "trend": 0.0,
                    "last_review_at": None,
                    "next_review_at": None,
                    "last_interval_days": 1,
                    "difficulty_bias": 1.0,
                },
            )
        return output

    def update_node_mastery(self, user_id: str, node_id: str, updates: dict) -> None:
        """Update or insert mastery record for a specific user-node pair."""
        if self.is_postgres:
            # Postgres UPSERT
            fields = []
            values = []
            for k, v in updates.items():
                fields.append(f"{k} = %s")
                values.append(v)
            
            with self._connect() as conn:
                cur = conn.cursor()
                # Check if exists
                cur.execute("SELECT 1 FROM nodes_mastery WHERE user_id = %s AND node_id = %s", (user_id, node_id))
                if cur.fetchone():
                    sql = f"UPDATE nodes_mastery SET {', '.join(fields)} WHERE user_id = %s AND node_id = %s"
                    cur.execute(sql, (*values, user_id, node_id))
                else:
                    cols = ["user_id", "node_id"] + list(updates.keys())
                    placeholders = ",".join(["%s"] * len(cols))
                    sql = f"INSERT INTO nodes_mastery ({','.join(cols)}) VALUES ({placeholders})"
                    cur.execute(sql, (user_id, node_id, *updates.values()))
        else:
            # SQLite UPSERT
            fields = []
            values = []
            for k, v in updates.items():
                fields.append(f"{k} = ?")
                values.append(v)

            with self._connect() as conn:
                row = conn.execute(
                    "SELECT 1 FROM nodes_mastery WHERE user_id = ? AND node_id = ?",
                    (user_id, node_id),
                ).fetchone()

                if row:
                    sql = f"UPDATE nodes_mastery SET {', '.join(fields)} WHERE user_id = ? AND node_id = ?"
                    conn.execute(sql, (*values, user_id, node_id))
                else:
                    cols = ["user_id", "node_id"] + list(updates.keys())
                    placeholders = ",".join(["?"] * len(cols))
                    sql = f"INSERT INTO nodes_mastery ({','.join(cols)}) VALUES ({placeholders})"
                    conn.execute(sql, (user_id, node_id, *updates.values()))

    def record_quiz_history(
        self,
        user_id: str,
        node_id: str,
        question: str,
        expected: str,
        user_answer: str,
        is_correct: bool,
        difficulty: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            if self.is_postgres:
                conn.cursor().execute(
                    """
                    INSERT INTO quiz_history 
                    (user_id, node_id, question, expected_answer, user_answer, is_correct, difficulty, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        node_id,
                        question,
                        expected,
                        user_answer,
                        1 if is_correct else 0,
                        difficulty,
                        now,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO quiz_history 
                    (user_id, node_id, question, expected_answer, user_answer, is_correct, difficulty, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        node_id,
                        question,
                        expected,
                        user_answer,
                        1 if is_correct else 0,
                        difficulty,
                        now,
                    ),
                )

    def get_recommended_difficulty(self, mastery: float) -> str:
        if mastery < 0.35:
            return "easy"
        if mastery < 0.7:
            return "medium"
        return "hard"

    def record_quiz_result(
        self,
        user_id: str,
        node_id: str,
        question: str,
        expected_answer: str,
        user_answer: str,
        is_correct: bool,
        difficulty: str,
    ) -> dict:
        self.ensure_user(user_id)
        state = self.get_mastery_by_node(user_id, [node_id])[node_id]

        mastery = float(state["mastery"])
        attempts = int(state["attempts"])
        correct_attempts = int(state["correct_attempts"])
        previous_interval = int(state["last_interval_days"] or 1)

        mastery, slip, guess, learn_rate = self.bkt_update(
            mastery=mastery, is_correct=is_correct, difficulty=difficulty
        )
        if is_correct:
            correct_attempts += 1
            next_interval = max(1, int(previous_interval * (1.7 + mastery)))
        else:
            next_interval = 1
        attempts += 1
        trend = (correct_attempts / attempts) if attempts else 0.0

        now = datetime.now(UTC)
        next_review = now + timedelta(days=next_interval)

        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                # Use Postgres ON CONFLICT UPSERT for Phase 4 (no duplicates, atomic)
                cur.execute(
                    """
                    INSERT INTO nodes_mastery (
                        user_id, node_id, mastery, attempts, correct_attempts,
                        last_result, trend, last_review_at, next_review_at,
                        last_interval_days, difficulty_bias
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, node_id) DO UPDATE SET
                        mastery = EXCLUDED.mastery,
                        attempts = EXCLUDED.attempts,
                        correct_attempts = EXCLUDED.correct_attempts,
                        last_result = EXCLUDED.last_result,
                        trend = EXCLUDED.trend,
                        last_review_at = EXCLUDED.last_review_at,
                        next_review_at = EXCLUDED.next_review_at,
                        last_interval_days = EXCLUDED.last_interval_days,
                        difficulty_bias = EXCLUDED.difficulty_bias
                    """,
                    (
                        user_id,
                        node_id,
                        mastery,
                        attempts,
                        correct_attempts,
                        1 if is_correct else 0,
                        trend,
                        now.isoformat(),
                        next_review.isoformat(),
                        next_interval,
                        learn_rate,
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO quiz_history (
                        user_id, node_id, question, expected_answer, user_answer,
                        is_correct, difficulty, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        node_id,
                        question,
                        expected_answer,
                        user_answer,
                        1 if is_correct else 0,
                        difficulty,
                        now.isoformat(),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO nodes_mastery (
                        user_id,
                        node_id,
                        mastery,
                        attempts,
                        correct_attempts,
                        last_result,
                        trend,
                        last_review_at,
                        next_review_at,
                        last_interval_days,
                        difficulty_bias
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        node_id,
                        mastery,
                        attempts,
                        correct_attempts,
                        1 if is_correct else 0,
                        trend,
                        now.isoformat(),
                        next_review.isoformat(),
                        next_interval,
                        learn_rate,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO quiz_history (
                        user_id,
                        node_id,
                        question,
                        expected_answer,
                        user_answer,
                        is_correct,
                        difficulty,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        node_id,
                        question,
                        expected_answer,
                        user_answer,
                        1 if is_correct else 0,
                        difficulty,
                        now.isoformat(),
                    ),
                )

        return {
            "user_id": user_id,
            "node_id": node_id,
            "mastery": mastery,
            "attempts": attempts,
            "correct_attempts": correct_attempts,
            "trend": trend,
            "next_review_at": next_review.isoformat(),
            "recommended_difficulty": self.get_recommended_difficulty(mastery),
        }

    @staticmethod
    def bkt_update(
        mastery: float, is_correct: bool, difficulty: str
    ) -> tuple[float, float, float, float]:
        base_slip = 0.1
        base_guess = 0.2
        base_learn = 0.12

        difficulty_adjust = {"easy": -0.04, "medium": 0.0, "hard": 0.06}.get(
            difficulty, 0.0
        )
        slip = min(0.3, max(0.02, base_slip + difficulty_adjust))
        guess = min(0.35, max(0.05, base_guess - difficulty_adjust))
        learn_rate = min(0.3, max(0.05, base_learn - (difficulty_adjust / 2)))

        prior = min(0.99, max(0.01, mastery))
        if is_correct:
            denom = (prior * (1 - slip)) + ((1 - prior) * guess)
            posterior = (prior * (1 - slip)) / denom if denom else prior
        else:
            denom = (prior * slip) + ((1 - prior) * (1 - guess))
            posterior = (prior * slip) / denom if denom else prior

        updated = posterior + (1 - posterior) * learn_rate
        return min(1.0, max(0.0, updated)), slip, guess, learn_rate

    @staticmethod
    def estimate_learning_gain(
        prior_mastery: float, is_correct: bool, difficulty: str
    ) -> float:
        updated, _, _, _ = LearnerTracker.bkt_update(
            mastery=prior_mastery, is_correct=is_correct, difficulty=difficulty
        )
        return max(0.0, updated - prior_mastery)

    def learner_progress(self, user_id: str) -> dict:
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT *
                    FROM nodes_mastery
                    WHERE user_id = %s
                    ORDER BY mastery ASC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT node_id, mastery, next_review_at
                    FROM nodes_mastery
                    WHERE user_id = %s
                      AND next_review_at IS NOT NULL
                      AND next_review_at <= %s
                    ORDER BY next_review_at ASC
                    LIMIT 10
                    """,
                    (user_id, datetime.now(UTC).isoformat()),
                )
                due_rows = cur.fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM nodes_mastery
                    WHERE user_id = ?
                    ORDER BY mastery ASC
                    """,
                    (user_id,),
                ).fetchall()

                due_rows = conn.execute(
                    """
                    SELECT node_id, mastery, next_review_at
                    FROM nodes_mastery
                    WHERE user_id = ?
                      AND next_review_at IS NOT NULL
                      AND next_review_at <= ?
                    ORDER BY next_review_at ASC
                    LIMIT 10
                    """,
                    (user_id, datetime.now(UTC).isoformat()),
                ).fetchall()

        node_states = [dict(row) for row in rows]
        avg_mastery = (
            sum(float(row["mastery"]) for row in rows) / len(rows) if rows else 0.0
        )
        weak_nodes = [dict(row) for row in rows if float(row["mastery"]) < 0.5]

        return {
            "user_id": user_id,
            "tracked_nodes": len(node_states),
            "average_mastery": avg_mastery,
            "weak_nodes": weak_nodes[:10],
            "due_for_review": [dict(row) for row in due_rows],
            "nodes": node_states,
        }

    # ── Quiz Session & Learner Profile Methods ─────────────────────────────

    def record_quiz_session(
        self,
        user_id: str,
        topic: str,
        difficulty: str,
        score: int,
        total: int,
        time_taken: int,
        feedback: str,
    ) -> dict:
        """Record a completed quiz session and update learner_profile automatically."""
        self.ensure_user(user_id)
        percentage = round((score / max(total, 1)) * 100, 2)
        now = datetime.now(UTC).isoformat()

        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO quiz_sessions
                        (user_id, topic, difficulty, num_questions, score, total,
                         percentage, time_taken, feedback, taken_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, topic, difficulty, total, score, total,
                     percentage, time_taken, feedback, now),
                )
                session_id = cur.fetchone()["id"]

                cur.execute(
                    """
                    INSERT INTO learner_profile (user_id, topic, mastery_score, quizzes_taken, avg_score, last_updated)
                    VALUES (%s, %s, %s, 1, %s, %s)
                    ON CONFLICT (user_id, topic) DO UPDATE SET
                        quizzes_taken = learner_profile.quizzes_taken + 1,
                        avg_score = ROUND(((learner_profile.avg_score * learner_profile.quizzes_taken) + EXCLUDED.avg_score) / (learner_profile.quizzes_taken + 1), 2),
                        mastery_score = ROUND((0.7 * learner_profile.mastery_score) + (0.3 * EXCLUDED.mastery_score), 2),
                        last_updated = EXCLUDED.last_updated
                    """,
                    (user_id, topic, percentage, percentage, now),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO quiz_sessions
                        (user_id, topic, difficulty, num_questions, score, total,
                         percentage, time_taken, feedback, taken_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, topic, difficulty, total, score, total,
                     percentage, time_taken, feedback, now),
                )
                session_id = cursor.lastrowid

                # Upsert learner_profile: weighted update of mastery & avg_score
                existing = conn.execute(
                    "SELECT * FROM learner_profile WHERE user_id = ? AND topic = ?",
                    (user_id, topic),
                ).fetchone()

                if existing:
                    q = existing["quizzes_taken"] + 1
                    new_avg = round(
                        (existing["avg_score"] * existing["quizzes_taken"] + percentage) / q, 2
                    )
                    # Mastery blends old mastery with new score (EMA, alpha=0.3)
                    new_mastery = round(
                        0.7 * existing["mastery_score"] + 0.3 * percentage, 2
                    )
                    conn.execute(
                        """
                        UPDATE learner_profile
                        SET mastery_score=?, quizzes_taken=?, avg_score=?, last_updated=?
                        WHERE user_id=? AND topic=?
                        """,
                        (new_mastery, q, new_avg, now, user_id, topic),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO learner_profile
                            (user_id, topic, mastery_score, quizzes_taken, avg_score, last_updated)
                        VALUES (?, ?, ?, 1, ?, ?)
                        """,
                        (user_id, topic, percentage, percentage, now),
                    )

        return {
            "session_id": session_id,
            "user_id": user_id,
            "topic": topic,
            "score": score,
            "total": total,
            "percentage": percentage,
            "time_taken": time_taken,
        }

    def get_learner_profile(self, user_id: str) -> dict:
        """Return the full learner profile including per-topic mastery."""
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT topic, mastery_score, quizzes_taken, avg_score, last_updated
                    FROM learner_profile
                    WHERE user_id = %s
                    ORDER BY mastery_score DESC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT topic, mastery_score, quizzes_taken, avg_score, last_updated
                    FROM learner_profile
                    WHERE user_id = ?
                    ORDER BY mastery_score DESC
                    """,
                    (user_id,),
                ).fetchall()

        topics = [dict(row) for row in rows]
        total_quizzes = sum(t["quizzes_taken"] for t in topics)
        overall = (
            sum(t["mastery_score"] for t in topics) / len(topics) if topics else 0.0
        )
        return {
            "user_id": user_id,
            "topics": topics,
            "overall_mastery": round(overall, 2),
            "total_quizzes": total_quizzes,
        }

    def update_topic_mastery(self, user_id: str, topic: str, mastery_score: float) -> dict:
        """Manually set mastery score for a topic (used by /learner/update)."""
        self.ensure_user(user_id)
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO learner_profile (user_id, topic, mastery_score, last_updated)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(user_id, topic) DO UPDATE SET
                        mastery_score=EXCLUDED.mastery_score,
                        last_updated=EXCLUDED.last_updated
                    """,
                    (user_id, topic, mastery_score, now),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO learner_profile (user_id, topic, mastery_score, last_updated)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, topic) DO UPDATE SET
                        mastery_score=excluded.mastery_score,
                        last_updated=excluded.last_updated
                    """,
                    (user_id, topic, mastery_score, now),
                )
        return {"user_id": user_id, "topic": topic, "mastery_score": mastery_score}

    def get_quiz_history(self, user_id: str, limit: int = 20) -> list[dict]:
        """Return recent quiz sessions for a user."""
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, topic, difficulty, score, total, percentage, time_taken, taken_at
                    FROM quiz_sessions
                    WHERE user_id = %s
                    ORDER BY taken_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
                rows = cur.fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, topic, difficulty, score, total, percentage, time_taken, taken_at
                    FROM quiz_sessions
                    WHERE user_id = ?
                    ORDER BY taken_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    # ── QUIZ STORAGE ───────────────────────────────────────────────────

    def save_generated_quiz(self, quiz_id: str, data: str) -> None:
        """Store a generated quiz in the DB."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            if self.is_postgres:
                conn.cursor().execute(
                    "INSERT INTO generated_quizzes (quiz_id, data, created_at) VALUES (%s, %s, %s)",
                    (quiz_id, data, now),
                )
            else:
                conn.execute(
                    "INSERT INTO generated_quizzes (quiz_id, data, created_at) VALUES (?, ?, ?)",
                    (quiz_id, data, now),
                )

    def get_generated_quiz(self, quiz_id: str) -> str | None:
        """Retrieve a generated quiz from the DB."""
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute("SELECT data FROM generated_quizzes WHERE quiz_id = %s", (quiz_id,))
                row = cur.fetchone()
            else:
                row = conn.execute(
                    "SELECT data FROM generated_quizzes WHERE quiz_id = ?",
                    (quiz_id,),
                ).fetchone()
        return row[0] if row else None

    # ── ANALYTICS & FEEDBACK ───────────────────────────────────────────

    def record_feedback(self, user_id: str, feedback: str, rating: int | None = None) -> None:
        """Store user feedback in the DB."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            if self.is_postgres:
                conn.cursor().execute(
                    "INSERT INTO user_feedback (user_id, feedback, rating, created_at) VALUES (%s, %s, %s, %s)",
                    (user_id, feedback, rating, now),
                )
            else:
                conn.execute(
                    "INSERT INTO user_feedback (user_id, feedback, rating, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, feedback, rating, now),
                )

    def get_system_wide_stats(self) -> dict:
        """Aggregate system-wide usage statistics (Phase 5)."""
        with self._connect() as conn:
            try:
                if self.is_postgres:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM users")
                    total_users = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM quiz_sessions")
                    total_quizzes = cur.fetchone()[0]
                    cur.execute("SELECT AVG(percentage) FROM quiz_sessions")
                    avg_score = cur.fetchone()[0] or 0.0
                    cur.execute("SELECT COUNT(*) FROM user_feedback")
                    total_feedback = cur.fetchone()[0]
                    
                    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
                    cur.execute(
                        "SELECT COUNT(DISTINCT user_id) FROM quiz_sessions WHERE taken_at > %s", 
                        (yesterday,)
                    )
                    active_24h = cur.fetchone()[0]
                else:
                    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    total_quizzes = conn.execute("SELECT COUNT(*) FROM quiz_sessions").fetchone()[0]
                    avg_score = conn.execute("SELECT AVG(percentage) FROM quiz_sessions").fetchone()[0] or 0.0
                    total_feedback = conn.execute("SELECT COUNT(*) FROM user_feedback").fetchone()[0]
                    
                    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
                    active_24h = conn.execute(
                        "SELECT COUNT(DISTINCT user_id) FROM quiz_sessions WHERE taken_at > ?", 
                        (yesterday,)
                    ).fetchone()[0]

                return {
                    "total_users": total_users,
                    "total_quizzes_taken": total_quizzes,
                    "average_quiz_score": round(float(avg_score), 2),
                    "total_feedback_entries": total_feedback,
                    "active_users_24h": active_24h,
                    "timestamp": datetime.now(UTC).isoformat()
                }
            except Exception as e:
                logger.error(f"Failed to fetch system stats: {e}")
                return {
                    "total_users": 0,
                    "total_quizzes_taken": 0,
                    "average_quiz_score": 0.0,
                    "total_feedback_entries": 0,
                    "active_users_24h": 0,
                    "timestamp": datetime.now(UTC).isoformat()
                }

    # ── Analytics & Event Tracking (Phase 1 & 2) ─────────────────────────

    def track_event(self, user_id: str, event_type: str, metadata: dict | None = None) -> None:
        """Log a user event to the database."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO user_events (user_id, event_type, timestamp, metadata) VALUES (%s, %s, %s, %s)",
                    (user_id, event_type, now, json.dumps(metadata) if metadata else None)
                )
            else:
                conn.execute(
                    "INSERT INTO user_events (user_id, event_type, timestamp, metadata) VALUES (?, ?, ?, ?)",
                    (user_id, event_type, now, json.dumps(metadata) if metadata else None)
                )

    def track_metric(self, metric_name: str, value: float, metadata: dict | None = None) -> None:
        """Log a system metric to the database."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO usage_metrics (metric_name, value, timestamp, metadata) VALUES (%s, %s, %s, %s)",
                    (metric_name, value, now, json.dumps(metadata) if metadata else None)
                )
            else:
                conn.execute(
                    "INSERT INTO usage_metrics (metric_name, value, timestamp, metadata) VALUES (?, ?, ?, ?)",
                    (metric_name, value, now, json.dumps(metadata) if metadata else None)
                )

    def get_user_analytics(self, user_id: str) -> dict:
        """Compute learning insights for a specific user (Phase 3)."""
        with self._connect() as conn:
            if self.is_postgres:
                cur = conn.cursor()
                # Improvement over time: quiz scores chronologically
                cur.execute(
                    "SELECT percentage, taken_at FROM quiz_sessions WHERE user_id = %s ORDER BY taken_at ASC",
                    (user_id,)
                )
                history = cur.fetchall()
                
                # Weak topics: topics with mastery < 0.5
                cur.execute(
                    "SELECT topic, mastery_score FROM learner_profile WHERE user_id = %s AND mastery_score < 50.0 ORDER BY mastery_score ASC",
                    (user_id,)
                )
                weak_topics = cur.fetchall()
                
                # Average score
                cur.execute("SELECT AVG(percentage) FROM quiz_sessions WHERE user_id = %s", (user_id,))
                avg_score = cur.fetchone()[0] or 0.0
            else:
                history = conn.execute(
                    "SELECT percentage, taken_at FROM quiz_sessions WHERE user_id = ? ORDER BY taken_at ASC",
                    (user_id,)
                ).fetchall()
                
                weak_topics = conn.execute(
                    "SELECT topic, mastery_score FROM learner_profile WHERE user_id = ? AND mastery_score < 50.0 ORDER BY mastery_score ASC",
                    (user_id,)
                ).fetchall()
                
                avg_score = conn.execute(
                    "SELECT AVG(percentage) FROM quiz_sessions WHERE user_id = ?",
                    (user_id,)
                ).fetchone()[0] or 0.0

        return {
            "user_id": user_id,
            "average_score": round(float(avg_score), 2),
            "score_history": [dict(h) for h in history],
            "weak_topics": [dict(w) for w in weak_topics],
            "timestamp": datetime.now(UTC).isoformat()
        }

