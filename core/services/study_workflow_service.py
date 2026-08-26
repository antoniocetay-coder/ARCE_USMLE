from __future__ import annotations

from typing import Any

import config
from core.ai.engine import (
    desmistificar_distratores,
    explicar_duvida_tutor,
    explicar_socratico,
    extrair_perola_hy,
    gerar_mnemonico_ia,
)
from core.ai.flashcard_generator import (
    gerar_flashcard_sob_demanda,
    gerar_flashcards_do_tutor,
    gerar_mais_flashcards,
    orquestrar_flashcards,
)
from core.repositories.flashcard_repository import FlashcardRepository
from core.repositories.analytics_repository import AnalyticsRepository
from core.repositories.pearl_repository import PearlRepository
from state.study_session import StudySession


class StudyWorkflowService:
    """Application facade for study-page callbacks; keeps persistence and AI out of UI."""

    def existing_flashcards(self, tags: list[str]) -> list[dict[str, Any]]:
        return FlashcardRepository(config.DB_PATH).get_by_tags(tags)

    def record_confusion(self, correct_tag: str, confused_tag: str) -> None:
        from core.repositories.question_repository import QuestionRepository
        QuestionRepository(config.DB_PATH).register_confusion(correct_tag, confused_tag)

    def generate_flashcards(self, kind: str, question: dict[str, Any], session: StudySession, existing: list[dict[str, Any]], request: str = "", target_count: int | None = None) -> list[dict[str, Any]]:
        from core.ai.flashcard_generator import gerar_flashcard_por_reflexao_erro
        if kind == "metacognitive":
            return gerar_flashcard_por_reflexao_erro(question, request, session.selected_answer or "", bool(session.is_correct), existing, session.draft_flashcards, target_count=target_count)
        if kind == "error":
            return orquestrar_flashcards(question, session.selected_answer or "", bool(session.is_correct), session.confidence or "", existing, session.draft_flashcards, target_count=target_count)
        if kind == "more":
            return gerar_mais_flashcards(question, existing, session.draft_flashcards, target_count=target_count)
        return gerar_flashcard_sob_demanda(question, request, existing, session.draft_flashcards, target_count=target_count)

    def generate_tutor_flashcards(self, tutor_response: str, card: dict[str, Any], drafts: list[dict[str, Any]], target_count: int | None = None) -> list[dict[str, Any]]:
        return gerar_flashcards_do_tutor(tutor_response, [card], drafts, target_count=target_count)

    def ask_tutor(self, material: str, doubt: str) -> str:
        return explicar_duvida_tutor(material, doubt)

    def ask_socratic(self, material: str, doubt: str) -> str:
        return explicar_socratico(material, doubt)

    def generate_mnemonic(self, material: str, estilo: str = "Dual-Coding Visual") -> str:
        return gerar_mnemonico_ia(material, estilo)

    def demystify_distractors(self, question: dict[str, Any]) -> str:
        return desmistificar_distratores(question)

    def extract_pearl(self, material: str) -> str:
        return extrair_perola_hy(material)

    def save_pearl(self, pearl_text: str, system: str) -> int:
        return PearlRepository().salvar_perola(pearl_text, system)

    def get_saved_pearls(self) -> list[dict[str, Any]]:
        return PearlRepository().get_todas_perolas()



    def save_flashcards_to_session(self, session: StudySession, drafts: list[tuple[str, str, list[str]]], system: str) -> int:
        saved = 0
        repo = FlashcardRepository()
        for front, back, tags in drafts:
            f_clean = str(front).strip()
            b_clean = str(back).strip()
            if not f_clean or not b_clean:
                continue
            card = repo.save_flashcard(f_clean, b_clean, system, tags)
            card_id = int(card["id"]) if isinstance(card, dict) else int(card)
            item = {
                "type": "flashcard",
                "item": {
                    "id": card_id,
                    "front": f_clean,
                    "back": b_clean,
                    "sistema": system,
                    "tag_list": "|".join(tags),
                    "difficulty": 5.0,
                    "stability": 1.0,
                    "repetitions": 0,
                    "lapses": 0,
                },
                "source": "generated",
            }
            if session.append_item(item):
                saved += 1
        return saved
