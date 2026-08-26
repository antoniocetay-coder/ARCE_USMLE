from __future__ import annotations

import pytest

import database
from ai.client import GeminiConfigurationError
from core.exceptions import QuestionGenerationError


def _question() -> dict:
    return {
        "vignette": "A patient has a clinical presentation.",
        "options": ["A) Correct", "B) Incorrect"],
        "correct": "A",
        "explanations": {"A": "Correct explanation", "B": "Incorrect explanation"},
        "educational_objective": "Recognize the diagnosis.",
        "content_tags": ["Test tag"],
    }


def test_plan_generation_persists_pending_questions_and_builds_queue(tmp_path, monkeypatch) -> None:
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

    monkeypatch.setattr(generation_module, "load_ai_settings", lambda: type("Settings", (), {"api_key": "test-key", "question_model": "gemini-3.5-flash"})())
    monkeypatch.setattr(generation_module, "gerar_lote_questoes", lambda system, difficulty, order, tags, quantity: [_question()])

    rows = QuestionGenerationService().generate_study_plan_questions(
        systems=["Cardiovascular"],
        tags=["Test tag"],
        difficulty="Medium",
        cognitive_order="2nd Order",
        quantity=1,
    )

    assert len(rows) == 1
    assert rows[0]["status"] == "pending"
    assert rows[0]["sistema"] == "Cardiovascular"
    assert QuestionGenerationService.build_study_queue(rows) == [{"type": "question", "item": rows[0]}]


def test_generation_without_key_raises_a_user_safe_error(tmp_path, monkeypatch) -> None:
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

    monkeypatch.setattr(generation_module, "load_ai_settings", lambda: type("Settings", (), {"api_key": None, "question_model": "gemini-3.5-flash"})())

    with pytest.raises(GeminiConfigurationError, match="chave Gemini"):
        QuestionGenerationService().generate_study_plan_questions(["Cardiovascular"], ["Test tag"], "Medium", "2nd Order", 1)


def test_invalid_model_is_rejected_before_calling_gemini(tmp_path, monkeypatch) -> None:
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

    monkeypatch.setattr(generation_module, "load_ai_settings", lambda: type("Settings", (), {"api_key": "test-key", "question_model": "models/gemini-3.5-flash"})())

    with pytest.raises(GeminiConfigurationError, match="modelo Gemini configurado é inválido"):
        QuestionGenerationService().generate_study_plan_questions(["Cardiovascular"], ["Test tag"], "Medium", "2nd Order", 1)


def test_invalid_gemini_question_does_not_persist_a_partial_batch(tmp_path, monkeypatch) -> None:
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

    monkeypatch.setattr(generation_module, "load_ai_settings", lambda: type("Settings", (), {"api_key": "test-key", "question_model": "gemini-3.5-flash"})())
    monkeypatch.setattr(generation_module, "gerar_lote_questoes", lambda *args: [{"vignette": "invalid"}])

    with pytest.raises(QuestionGenerationError, match="não retornou questões válidas"):
        QuestionGenerationService().generate_study_plan_questions(["Cardiovascular"], ["Test tag"], "Medium", "2nd Order", 1)
    from core.repositories.question_repository import QuestionRepository
    assert QuestionRepository(tmp_path / "study.db").get_pending_questions() == []


def test_plan_success_populates_a_fresh_study_session() -> None:
    from core.question_generation_service import QuestionGenerationService
    from state.study_session import StudySession

    session = StudySession(mode="old", queue=[{"type": "question", "item": {"id": 99}}], current_index=1)
    row = {"id": 1, "status": "pending"}

    QuestionGenerationService.populate_study_session(session, "Plano cardíaco", [row])

    assert session.mode == "Plano cardíaco"
    assert session.current_index == 0
    assert session.queue == [{"type": "question", "item": row}]
