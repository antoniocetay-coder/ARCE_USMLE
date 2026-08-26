from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from core.exceptions import StudySessionError

ItemType = Literal["question", "flashcard"]
MAX_SAME_SESSION_REPEATS = 3


@dataclass
class StudyQueueItem:
    item_type: ItemType
    item_id: str
    source: str
    payload: dict[str, Any]
    same_session_attempts: int = 0
    last_grade: str | None = None

    @classmethod
    def from_legacy(cls, value: dict[str, Any]) -> StudyQueueItem:
        if "item_type" in value:
            return cls(**value)
        item = value.get("item", value)
        item_type = value.get("type", "question")
        identifier = item.get("id") if isinstance(item, dict) else None
        return cls(item_type=item_type, item_id=f"{item_type}:{identifier}", source="legacy", payload=item)


@dataclass
class StudySession:
    mode: str | None = None
    queue: list[StudyQueueItem] = field(default_factory=list)
    current_index: int = 0
    started_at: str | None = None
    answer_submitted: bool = False
    selected_answer: str | None = None
    is_correct: bool | None = None
    confidence: str | None = None
    time_started: float | None = None
    time_taken: int | None = None
    reveal_flashcard: bool = False
    draft_flashcards: list[dict[str, Any]] = field(default_factory=list)
    tutor_response: str | None = None

    @property
    def current_item(self) -> StudyQueueItem | None:
        return self.queue[self.current_index] if 0 <= self.current_index < len(self.queue) else None

    def remaining_count(self) -> int:
        return max(0, len(self.queue) - self.current_index)

    def append_item(self, item: StudyQueueItem) -> bool:
        if any(existing.item_id == item.item_id for existing in self.queue):
            return False
        self.queue.append(item)
        return True

    def requeue_item(self, item: StudyQueueItem, grade: str) -> bool:
        grade = grade.title()
        item.last_grade = grade
        limit = MAX_SAME_SESSION_REPEATS if grade == "Again" else 1 if grade == "Hard" else 0
        if item.same_session_attempts >= limit:
            return False
        item.same_session_attempts += 1
        self.queue.append(item)
        return True

    def advance(self) -> None:
        if self.current_item is None:
            raise StudySessionError("There is no active study item to advance.")
        self.current_index += 1
        self._clear_item_ui_state()

    def begin_question_timer(self, now: float) -> None:
        if self.time_started is None:
            self.time_started = now

    def record_question_submission(self, selected_answer: str, confidence: str, time_taken: int, is_correct: bool) -> bool:
        if self.answer_submitted:
            return False
        self.answer_submitted, self.selected_answer = True, selected_answer
        self.confidence, self.time_taken, self.is_correct = confidence, time_taken, is_correct
        return True

    def end(self) -> None:
        self.mode = None
        self.queue.clear()
        self.current_index = 0
        self.started_at = None
        self._clear_item_ui_state()
        self.draft_flashcards.clear()
        self.tutor_response = None

    reset = end

    def _clear_item_ui_state(self) -> None:
        self.answer_submitted = False
        self.selected_answer = None
        self.is_correct = None
        self.confidence = None
        self.time_started = None
        self.time_taken = None
        self.reveal_flashcard = False
        self.draft_flashcards.clear()
        self.tutor_response = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> StudySession:
        payload = payload or {}
        try:
            queue = [StudyQueueItem.from_legacy(value) for value in payload.get("queue", [])]
            session = cls(**{key: value for key, value in payload.items() if key in cls.__dataclass_fields__ and key != "queue"})
            session.queue = queue
            if session.current_index < 0 or session.current_index > len(queue):
                session.end()
            return session
        except (TypeError, ValueError, AttributeError):
            return cls()

    def start(self, mode: str, items: list[StudyQueueItem]) -> None:
        self.end()
        self.mode = mode
        self.started_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            self.append_item(item)
