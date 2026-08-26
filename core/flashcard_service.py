from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai.settings import load_ai_settings
from core.algorithms.fsrs import RatingPreview, calculate_card_preview
from core.repositories.flashcard_repository import FlashcardRepository


def review_flashcard(card: dict[str, Any], grade: int, rating_preview: RatingPreview | None = None) -> int:
    """
    Aplica a avaliação FSRS v5 e persiste o estado, estabilidade, dificuldade e vencimento.
    Retorna o número de dias de intervalo (arredondado para inteiro).
    """
    now = datetime.now(timezone.utc)
    retention = load_ai_settings().desired_retention

    if rating_preview is None:
        preview_data = calculate_card_preview(card, desired_retention=retention, now=now)
        rating_preview = preview_data.ratings.get(grade, preview_data.ratings[3])

    raw_reps = card.get("repetitions")
    raw_lapses = card.get("lapses")
    reps = (int(raw_reps) if raw_reps is not None else 0) + 1
    lapses = (int(raw_lapses) if raw_lapses is not None else 0) + (1 if grade == 1 else 0)

    due_str = rating_preview.due_datetime.strftime("%Y-%m-%d")
    now_iso = now.isoformat()

    raw_id = card.get("id")
    card_id = int(raw_id["id"]) if isinstance(raw_id, dict) else (int(raw_id) if raw_id is not None else None)
    
    if card_id is not None:
        FlashcardRepository().update_review(
            card_id=card_id,
            repetitions=reps,
            stability=rating_preview.new_stability,
            difficulty=rating_preview.new_difficulty,
            due=due_str,
            lapses=lapses,
            state=int(rating_preview.new_state),
            scheduled_days=rating_preview.interval_days,
            last_review_at=now_iso,
        )

    # Atualiza o objeto de memória local
    card["difficulty"] = rating_preview.new_difficulty
    card["stability"] = rating_preview.new_stability
    card["repetitions"] = reps
    card["lapses"] = lapses
    card["state"] = int(rating_preview.new_state)
    card["scheduled_days"] = rating_preview.interval_days
    card["last_review"] = due_str
    card["last_review_at"] = now_iso
    card["due"] = due_str

    return max(1, round(rating_preview.interval_days)) if rating_preview.interval_days >= 1.0 else 0
