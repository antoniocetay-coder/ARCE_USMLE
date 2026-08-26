from __future__ import annotations

import pytest

import database


@pytest.mark.parametrize("quantity", [5, 10, 15, 20])
def test_selected_batch_uses_exactly_one_ai_call(tmp_path, monkeypatch, quantity: int) -> None:
    db_path = tmp_path / "study.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    try:
        ApplicationRepository(db_path).initialize()
    except NameError:
        pass

    import core.question_generation_service as generation_module
    from core.question_generation_service import QuestionGenerationService

    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        generation_module,
        "load_ai_settings",
        lambda: type("Settings", (), {"api_key": "test-key", "question_model": "gemini-3.5-flash"})(),
    )

    def generate_once(system: str, difficulty: str, cognitive_order: str, tags: list[str], requested: int) -> list[dict]:
        calls.append((system, requested))
        return [
            {
                "vignette": f"Question {index}",
                "options": ["A) Correct", "B) Incorrect"],
                "correct": "A",
                "explanations": {"A": "Correct", "B": "Incorrect"},
                "educational_objective": "Recognize the diagnosis.",
                "content_tags": ["Test tag"],
            }
            for index in range(requested)
        ]

    monkeypatch.setattr(generation_module, "gerar_lote_questoes", generate_once)
    rows = QuestionGenerationService().generate_study_plan_questions(
        systems=["Cardiovascular", "Respiratory"],
        tags=["Test tag"],
        difficulty="Medium",
        cognitive_order="2nd Order",
        quantity=quantity,
    )

    assert len(calls) == 1
    assert calls[0][1] == quantity
    assert len(rows) == quantity
