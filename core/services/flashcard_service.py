from __future__ import annotations

from datetime import datetime, timezone

import config
from core.algorithms.fsrs import calculate_fsrs
from core.models.study_session import StudySession
from core.repositories.flashcard_repository import FlashcardRepository


class FlashcardService:
    def __init__(self, repository: FlashcardRepository | None = None):
        self.repository = repository or FlashcardRepository(config.DB_PATH)

    def save_and_append(self, session: StudySession, front: str, back: str, system: str, tags: list[str], source: str = "generated") -> bool:
        from core.models.study_session import StudyQueueItem
        card = self.repository.save_flashcard(front, back, system, tags)
        return session.append_item(StudyQueueItem("flashcard", f"flashcard:{card['id']}", source, card))

    def review(self, session: StudySession, grade: int) -> tuple[int, bool]:
        item = session.current_item()
        if item is None or item.item_type != "flashcard":
            raise ValueError("No active flashcard.")
        card = item.payload
        last_review = datetime.fromisoformat(card.get("last_review") or datetime.now(timezone.utc).date().isoformat()).date()
        elapsed = max(0, (datetime.now(timezone.utc).date() - last_review).days)
        from ai.settings import load_ai_settings
        retention = load_ai_settings().desired_retention
        difficulty, stability, _, interval, repetitions, lapses = calculate_fsrs(grade, float(card.get("difficulty", 5)), float(card.get("stability", 1)), elapsed, int(card.get("repetitions", 0)), int(card.get("lapses", 0)), desired_retention=retention)
        due = (datetime.now(timezone.utc).date()).fromordinal(datetime.now(timezone.utc).date().toordinal() + interval).isoformat()

        self.repository.update_review(int(card["id"]), repetitions, stability, difficulty, due, lapses)
        requeued = session.requeue_item(item, {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}[grade])
        session.advance()
        return interval, requeued
