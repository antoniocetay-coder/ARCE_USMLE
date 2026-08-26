from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import config
from core.repositories.database import connection


class AISettingsRepository:
    """Persistence boundary for the singleton AI configuration."""

    def __init__(self, path: Path | str | None = None):
        self.path = path if path is not None else config.DB_PATH

    def load_configuration(self) -> dict[str, Any]:
        with connection(self.path) as conn:
            try:
                row = conn.execute("SELECT api_key, question_model, flashcard_model, desired_retention FROM ai_configuration WHERE id=1").fetchone()
                if row:
                    return dict(row)
            except sqlite3.OperationalError:
                row = conn.execute("SELECT api_key, question_model, flashcard_model FROM ai_configuration WHERE id=1").fetchone()
                if row:
                    d = dict(row)
                    d["desired_retention"] = 0.90
                    return d
            return {"api_key": None, "question_model": None, "flashcard_model": None, "desired_retention": 0.90}

    def save_configuration(self, api_key: str | None, question_model: str, flashcard_model: str, desired_retention: float = 0.90) -> None:
        with connection(self.path) as conn:
            try:
                try:
                    conn.execute("ALTER TABLE ai_configuration ADD COLUMN desired_retention REAL NOT NULL DEFAULT 0.90")
                except sqlite3.OperationalError:
                    pass
                conn.execute(
                    "INSERT INTO ai_configuration(id, api_key, question_model, flashcard_model, desired_retention) VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET api_key=excluded.api_key, question_model=excluded.question_model, flashcard_model=excluded.flashcard_model, desired_retention=excluded.desired_retention",
                    (api_key, question_model, flashcard_model, float(desired_retention)),
                )
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
