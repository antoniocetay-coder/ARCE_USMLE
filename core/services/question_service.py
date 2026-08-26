from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import config
from core.ai.question_generator import generate_questions
from core.ai.validators import validate_question
from core.exceptions import QuestionGenerationError
from core.models.study_session import StudyQueueItem, StudySession
from core.repositories.question_repository import QuestionRepository
from taxonomy import TAXONOMIA_COMPLETA

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationOutcome:
    rows: list[dict[str, Any]]
    accepted: int
    rejected: int
    errors: list[str]
    duplicate: bool = False


class QuestionGenerationService:
    def __init__(self, repository: QuestionRepository | None = None):
        self.repository = repository or QuestionRepository(config.DB_PATH)

    @staticmethod
    def _valid_tags(system: str) -> set[str]:
        return {tag for groups in TAXONOMIA_COMPLETA.get(system, {}).values() if isinstance(groups, list) for tag in groups}

    def generate_questions(self, systems: list[str], tags: list[str], difficulty: str, cognitive_order: str, quantity: int, *, request_id: str | None = None) -> GenerationOutcome:
        if not systems or quantity < 1:
            raise QuestionGenerationError("Plano de estudo inválido.")
        distribution = [quantity // len(systems)] * len(systems)
        for index in range(quantity % len(systems)):
            distribution[index] += 1
        entries: list[dict[str, Any]] = []
        errors: list[str] = []
        for system, count in zip(systems, distribution):
            for question in generate_questions(system, difficulty, cognitive_order, tags, count):
                result = validate_question(question, system, valid_tags=self._valid_tags(system))
                if result.is_valid:
                    entries.append({"sistema": system, "dificuldade": difficulty, "question": question})
                else:
                    errors.extend(result.errors)
                    logger.warning("Rejected invalid AI question for %s: %s", system, result.errors)
        if not entries:
            raise QuestionGenerationError("O Gemini não retornou questões estruturalmente válidas.")
        saved = self.repository.save_pending_questions_batch(entries, request_id=request_id or str(uuid.uuid4()))
        return GenerationOutcome(saved.rows, len(saved.rows), len(errors), errors, saved.duplicate)

    @staticmethod
    def build_study_queue(rows: list[dict[str, Any]]) -> list[StudyQueueItem]:
        return [StudyQueueItem("question", f"question:{row['id']}", "generated", row) for row in rows]

    def populate_study_session(self, session: StudySession, plan_title: str, rows: list[dict[str, Any]]) -> None:
        session.start(plan_title, self.build_study_queue(rows))
