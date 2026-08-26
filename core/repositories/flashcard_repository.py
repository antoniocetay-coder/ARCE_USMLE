from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from core.repositories.database import connection


class FlashcardRepository:
    def __init__(self, path: Path | str | None = None):
        self.path = path if path is not None else config.DB_PATH

    def save_flashcard(self, front: str, back: str, system: str, tags: Iterable[str]) -> dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        today = now_dt.strftime("%Y-%m-%d")
        now_iso = now_dt.isoformat()
        with connection(self.path) as conn:
            cursor = conn.execute(
                "INSERT INTO flashcards(front, back, sistema, tag_list) VALUES (?, ?, ?, ?)",
                (front, back, system, "|".join(tags)),
            )
            card_id = int(cursor.lastrowid)
            try:
                conn.execute(
                    """
                    INSERT INTO srs_state(object_id, object_type, repetitions, stability, difficulty, last_review, last_review_at, due, lapses, state, scheduled_days)
                    VALUES (?, 'flashcard', 0, 1.0, 5.0, ?, ?, ?, 0, 0, 0.0)
                    """,
                    (card_id, today, now_iso, today),
                )
            except Exception:
                conn.execute(
                    "INSERT INTO srs_state(object_id, object_type, last_review, due) VALUES (?, 'flashcard', ?, ?)",
                    (card_id, today, today),
                )
            return {"id": card_id, "front": front, "back": back, "sistema": system, "tag_list": "|".join(tags)}

    def get_due_flashcards(self) -> list[dict[str, Any]]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with connection(self.path) as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT f.*, s.repetitions, s.stability, s.difficulty, s.last_review, 
                           s.last_review_at, s.due, s.lapses, s.state, s.scheduled_days
                    FROM flashcards f 
                    JOIN srs_state s ON s.object_id = f.id AND s.object_type = 'flashcard' 
                    WHERE s.due <= ? 
                    ORDER BY s.due, f.id
                    """,
                    (today,),
                ).fetchall()
            except Exception:
                rows = conn.execute(
                    """
                    SELECT f.*, s.repetitions, s.stability, s.difficulty, s.last_review, s.due, s.lapses 
                    FROM flashcards f 
                    JOIN srs_state s ON s.object_id = f.id AND s.object_type = 'flashcard' 
                    WHERE s.due <= ? 
                    ORDER BY s.due, f.id
                    """,
                    (today,),
                ).fetchall()
            return [dict(row) for row in rows]

    def get_by_tags(self, tags: Iterable[str]) -> list[dict[str, Any]]:
        wanted = set(tags)
        with connection(self.path) as conn:
            return [
                dict(row)
                for row in conn.execute("SELECT * FROM flashcards ORDER BY id DESC")
                if wanted & set(row["tag_list"].split("|"))
            ]

    get_flashcards_by_tags = get_by_tags

    def update_review(
        self,
        card_id: int,
        repetitions: int,
        stability: float,
        difficulty: float,
        due: str,
        lapses: int,
        state: int = 2,
        scheduled_days: float = 1.0,
        last_review_at: str | None = None,
    ) -> None:
        now_dt = datetime.now(timezone.utc)
        today = now_dt.strftime("%Y-%m-%d")
        now_iso = last_review_at or now_dt.isoformat()
        with connection(self.path) as conn:
            try:
                conn.execute(
                    """
                    UPDATE srs_state 
                    SET repetitions = ?, stability = ?, difficulty = ?, 
                        last_review = ?, last_review_at = ?, due = ?, 
                        lapses = ?, state = ?, scheduled_days = ?
                    WHERE object_id = ? AND object_type = 'flashcard'
                    """,
                    (repetitions, stability, difficulty, today, now_iso, due, lapses, state, scheduled_days, card_id),
                )
            except Exception:
                conn.execute(
                    """
                    UPDATE srs_state 
                    SET repetitions = ?, stability = ?, difficulty = ?, 
                        last_review = ?, due = ?, lapses = ? 
                    WHERE object_id = ? AND object_type = 'flashcard'
                    """,
                    (repetitions, stability, difficulty, today, due, lapses, card_id),
                )

    update_flashcard_review = update_review

    def delete_flashcard(self, card_id: int) -> None:
        with connection(self.path) as conn:
            conn.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
            conn.execute("DELETE FROM srs_state WHERE object_id = ? AND object_type = 'flashcard'", (card_id,))
