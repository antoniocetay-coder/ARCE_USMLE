from __future__ import annotations

import json
from typing import Any

from ai.client import generate_text
from ai.settings import load_ai_settings
from core.ai.validators import extract_json
from core.exceptions import QuestionGenerationError
from taxonomy import TAXONOMIA_COMPLETA

PROMPT_VERSION = "2026-07-22.1"


def build_question_prompt(system: str, difficulty: str, cognitive_order: str, tags: list[str], quantity: int) -> str:
    taxonomy = json.dumps({system: TAXONOMIA_COMPLETA.get(system, {})}, ensure_ascii=False)
    return (
        f"PROMPT_VERSION: {PROMPT_VERSION}\nGenerate exactly {quantity} USMLE questions as JSON {{\"questions\":[]}}. "
        f"System: {system}. Difficulty: {difficulty}. Cognitive order: {cognitive_order}. Tags: {', '.join(tags)}. "
        f"Use only taxonomy tags: {taxonomy}. Every question needs vignette, 5 labeled options, correct, "
        "explanations for every option, educational_objective, content_tags, distractor_tags, difficulty and cognitive_order. Return JSON only."
    )


def generate_questions(system: str, difficulty: str, cognitive_order: str, tags: list[str], quantity: int) -> list[dict[str, Any]]:
    settings = load_ai_settings()
    text = generate_text(build_question_prompt(system, difficulty, cognitive_order, tags, quantity), settings.question_model, api_key=settings.api_key, response_json=True)
    payload = extract_json(text)
    if not payload:
        raise QuestionGenerationError("O Gemini retornou JSON inválido para as questões.")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise QuestionGenerationError("O Gemini retornou JSON inválido para as questões.") from error
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise QuestionGenerationError("O Gemini não retornou uma lista de questões.")
    for question in data["questions"]:
        question.setdefault("difficulty", difficulty)
        question.setdefault("cognitive_order", cognitive_order)
    return data["questions"]
