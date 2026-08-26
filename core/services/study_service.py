from __future__ import annotations

import json
from dataclasses import dataclass

import config
from core.exceptions import StudySessionError
from core.models.study_session import StudySession
from core.repositories.question_repository import QuestionRepository


@dataclass(frozen=True)
class AnswerResult:
    is_correct: bool
    elapsed_seconds: int
    persisted: bool


class StudyService:
    def __init__(self, repository: QuestionRepository | None = None):
        self.repository = repository or QuestionRepository(config.DB_PATH)

    def submit_answer(self, session: StudySession, selected_answer: str, confidence: str, started_at: float, ended_at: float) -> AnswerResult:
        if session.answer_submitted:
            return AnswerResult(bool(session.is_correct), int(session.time_taken or 0), False)
        current = session.current_item
        is_dict = isinstance(current, dict)
        item_type = current.get("type") if is_dict else getattr(current, "item_type", None)
        if not current or item_type != "question":
            raise StudySessionError("Não há uma questão ativa para responder.")
        row = current.get("item") if is_dict else getattr(current, "payload", {})
        if "question_json" in row:
            raw = row["question_json"]
            question = json.loads(raw) if isinstance(raw, str) else raw
        else:
            question = row
        answer = selected_answer.strip().upper()[:1]
        correct = answer == str(question.get("correct", "")).strip().upper()[:1]
        elapsed = max(0, int(ended_at - started_at))
        persisted = self.repository.record_question_result(int(row["id"]), row.get("sistema", "General_Principles"), correct, question.get("content_tags", []), elapsed, confidence)
        session.record_question_submission(selected_answer, confidence, elapsed, correct)
        return AnswerResult(correct, elapsed, persisted)

    @staticmethod
    def end_session(session: StudySession) -> None:
        session.end()
