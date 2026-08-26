from __future__ import annotations

import database
from core.services.study_service import StudyService
from state.study_session import StudySession


def test_submit_answer_persists_once_and_updates_session(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "study.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    ApplicationRepository(db_path).initialize()
    from core.repositories.question_repository import QuestionRepository
    question = {"vignette": "v", "options": ["A) x", "B) y"], "correct": "A", "explanations": {}, "educational_objective": "o", "content_tags": ["Tag"]}
    result = QuestionRepository(tmp_path / "study.db").save_pending_questions_batch([{"question": question, "sistema": "Renal", "dificuldade": "Easy"}], request_id="batch1")
    question_id = result.rows[0]["id"]
    session = StudySession(queue=[{"type": "question", "item": {"id": question_id, "sistema": "Renal", "question_json": __import__("json").dumps(question)}}])

    from core.repositories.question_repository import QuestionRepository
    service = StudyService(repository=QuestionRepository(tmp_path / "study.db"))

    result = service.submit_answer(session, "A", "Certeza Absoluta", started_at=0, ended_at=17)

    assert result.is_correct is True
    assert result.persisted is True
    assert session.answer_submitted is True
    assert service.submit_answer(session, "A", "Certeza Absoluta", 0, 18).persisted is False
