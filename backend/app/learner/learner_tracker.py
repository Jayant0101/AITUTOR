from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta


class LearnerTracker:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize_schema(self) -> None:
        with self._connect() as conn:
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
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Look up user by id. Returns dict or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_mastery_by_node(self, user_id: str, node_ids: list[str]) -> dict[str, dict]:
        if not node_ids:
            return {}

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
