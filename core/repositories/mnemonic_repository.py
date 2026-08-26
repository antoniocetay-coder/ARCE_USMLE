from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import config
from core.repositories.database import connection


class MnemonicRepository:
    """Repository for managing mnemonics."""

    def __init__(self, path: Path | str | None = None):
        self.path = path if path is not None else config.DB_PATH

    def salvar_mnemonico(self, title: str, content: str, sistema: str, structured_data: str | None = None) -> int:
        with connection(self.path) as conn:
            try:
                cursor = conn.execute("INSERT INTO mnemonics(title, content, sistema, structured_data) VALUES (?, ?, ?, ?)", (title, content, sistema, structured_data))
                conn.commit()
                return int(cursor.lastrowid)
            except sqlite3.Error:
                conn.rollback()
                raise

    def get_todos_mnemonicos(self) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM mnemonics ORDER BY id DESC").fetchall()]

    def atualizar_mnemonico(self, mnemonic_id: int, title: str, content: str, structured_data: str | None = None) -> None:
        with connection(self.path) as conn:
            try:
                if structured_data is not None:
                    conn.execute("UPDATE mnemonics SET title=?, content=?, structured_data=? WHERE id=?", (title, content, structured_data, mnemonic_id))
                else:
                    conn.execute("UPDATE mnemonics SET title=?, content=? WHERE id=?", (title, content, mnemonic_id))
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise

    def deletar_mnemonico(self, mnemonic_id: int) -> None:
        with connection(self.path) as conn:
            try:
                conn.execute("DELETE FROM mnemonics WHERE id=?", (mnemonic_id,))
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
