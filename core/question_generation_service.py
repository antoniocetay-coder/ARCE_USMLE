from __future__ import annotations

import logging
import re
from itertools import cycle
from typing import Any

from ai.client import GeminiConfigurationError
from ai.settings import load_ai_settings
import config
from core.ai.engine import gerar_lote_questoes
from core.ai.legacy_validation import validar_questao
from core.exceptions import QuestionGenerationError
from core.repositories.question_repository import QuestionRepository
from state.study_session import StudySession

logger = logging.getLogger(__name__)
_MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9.-]*$")


class QuestionGenerationService:
    """Generate, validate and persist question batches without UI dependencies."""

    @staticmethod
    def build_study_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"type": "question", "item": row} for row in rows]

    @classmethod
    def populate_study_session(cls, session: StudySession, plan_title: str, rows: list[dict[str, Any]]) -> None:
        session.reset()
        session.mode = plan_title
        session.queue = cls.build_study_queue(rows)

    def generate_study_plan_questions(
        self,
        systems: list[str],
        tags: list[str],
        difficulty: str,
        cognitive_order: str,
        quantity: int,
    ) -> list[dict[str, Any]]:
        self._validate_configuration()
        if not systems:
            raise ValueError("O plano não possui sistemas configurados.")
        if quantity < 1:
            raise ValueError("O plano precisa solicitar ao menos uma questão.")

        primary_system = systems[0]
        questions = gerar_lote_questoes(primary_system, difficulty, cognitive_order, tags, quantity)
        generated: list[dict[str, Any]] = []
        for question in questions:
            question.setdefault("difficulty", difficulty)
            question.setdefault("cognitive_order", cognitive_order)
            valid, reason = self._validate_question(question, primary_system)
            if not valid:
                logger.warning("Discarding invalid generated question for %s: %s", primary_system, reason)
                continue
            generated.append({"sistema": primary_system, "dificuldade": difficulty, "question": question})

        if not generated:
            raise QuestionGenerationError("O Gemini não retornou questões válidas para este plano.")
        import uuid
        return QuestionRepository(config.DB_PATH).save_pending_questions_batch(generated, request_id=str(uuid.uuid4())).rows

    @staticmethod
    def _validate_configuration() -> None:
        settings = load_ai_settings()
        if not settings.api_key:
            raise GeminiConfigurationError("Configure uma chave Gemini antes de gerar questões.")
        model = settings.question_model.strip()
        if not model or not _MODEL_ID.fullmatch(model) or model.startswith(("models.", "google.")):
            raise GeminiConfigurationError("O modelo Gemini configurado é inválido. Escolha ou informe um identificador válido.")

    @staticmethod
    def _validate_question(question: dict[str, Any], system: str) -> tuple[bool, str]:
        valid, reason = validar_questao(question, system)
        if not valid:
            return valid, reason
        if not isinstance(question.get("explanations"), dict) or not question["explanations"]:
            return False, "A questão não possui explicações válidas."
        if not str(question.get("educational_objective", "")).strip():
            return False, "A questão não possui objetivo educacional."
        if not str(question.get("difficulty", "")).strip() or not str(question.get("cognitive_order", "")).strip():
            return False, "A questão não possui dificuldade ou ordem cognitiva."
        return True, ""
