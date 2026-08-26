from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import config
from core.repositories.database import connection


class PearlRepository:
    """Repository for managing high-yield pearls."""

    def __init__(self, path: Path | str | None = None):
        self.path = path if path is not None else config.DB_PATH

    def salvar_perola(self, pearl_text: str, sistema: str) -> int:
        with connection(self.path) as conn:
            try:
                cursor = conn.execute("INSERT INTO high_yield_pearls(pearl_text, sistema) VALUES (?, ?)", (pearl_text, sistema))
                conn.commit()
                return int(cursor.lastrowid)
            except sqlite3.Error:
                conn.rollback()
                raise

    def get_todas_perolas(self) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM high_yield_pearls ORDER BY id DESC").fetchall()]
