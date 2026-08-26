from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import time
from typing import Any


@dataclass
class StudySession:
    """Mutable study state stored independently for each NiceGUI user."""

    mode: str | None = None
    queue: list[dict[str, Any]] = field(default_factory=list)
    current_index: int = 0
    answer_submitted: bool = False
    selected_answer: str | None = None
    is_correct: bool | None = None
    confidence: str | None = None
    time_started: float | None = None
    time_taken: int | None = None
    reveal_flashcard: bool = False
    draft_flashcards: list[dict[str, Any]] = field(default_factory=list)
    flashcards_saved: bool = False
    tutor_response: str | None = None
    mnemonic_response: str | None = None
    demystified_response: str | None = None
    pearl_response: str | None = None
    session_results: list[dict[str, Any]] = field(default_factory=list)



    @property
    def current_item(self) -> dict[str, Any] | None:
        return self.queue[self.current_index] if self.current_index < len(self.queue) else None

    def begin_question_timer(self) -> None:
        if self.time_started is None:
            self.time_started = time()

    def record_question_submission(
        self, selected_answer: str, confidence: str, time_taken: int, is_correct: bool
    ) -> bool:
        if self.answer_submitted:
            return False
        self.answer_submitted = True
        self.selected_answer = selected_answer
        self.confidence = confidence
        self.time_taken = time_taken
        self.is_correct = is_correct
        return True

    def append_item(self, item: dict[str, Any]) -> bool:
        """Append a unique study item at the end of the current queue."""
        candidate_id = item.get("item_id") or f"{item.get('type')}:{item.get('item', {}).get('id')}"
        if any((queued.get("item_id") or f"{queued.get('type')}:{queued.get('item', {}).get('id')}") == candidate_id for queued in self.queue):
            return False
        item["item_id"] = candidate_id
        item.setdefault("same_session_attempts", 0)
        item.setdefault("source", "session")
        self.queue.append(item)
        return True

    def requeue_item(self, item: dict[str, Any], grade: str) -> bool:
        limits = {"Again": 3, "Hard": 1, "Good": 0, "Easy": 0}
        limit = limits.get(grade, 0)
        attempts = int(item.get("same_session_attempts", 0))
        item["last_grade"] = grade
        if attempts >= limit:
            return False
        item["same_session_attempts"] = attempts + 1
        self.queue.append(item)
        return True

    def remaining_count(self) -> int:
        return max(0, len(self.queue) - self.current_index)

    def end(self) -> None:
        self.reset()

    def next_item(self) -> None:
        if self.answer_submitted:
            self.session_results.append({
                "is_correct": self.is_correct,
                "confidence": self.confidence,
                "time_taken": self.time_taken,
                "item_type": self.current_item.get("type") if self.current_item else None,
            })
            
        self.current_index += 1
        self.answer_submitted = False
        self.selected_answer = None
        self.is_correct = None
        self.confidence = None
        self.time_started = None
        self.time_taken = None
        self.reveal_flashcard = False
        self.draft_flashcards = []
        self.flashcards_saved = False
        self.tutor_response = None
        self.mnemonic_response = None
        self.demystified_response = None
        self.pearl_response = None

    def reset(self) -> None:
        self.mode = None
        self.queue = []
        self.current_index = 0
        self.answer_submitted = False
        self.selected_answer = None
        self.is_correct = None
        self.confidence = None
        self.time_started = None
        self.time_taken = None
        self.reveal_flashcard = False
        self.draft_flashcards = []
        self.flashcards_saved = False
        self.tutor_response = None
        self.mnemonic_response = None
        self.demystified_response = None
        self.pearl_response = None
        self.session_results = []




    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> StudySession:
        allowed = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in (payload or {}).items() if key in allowed})
