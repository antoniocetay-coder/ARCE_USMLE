from __future__ import annotations

from core.repositories.database import connection
import database
from core.repositories.question_repository import QuestionRepository
from core.repositories.flashcard_repository import FlashcardRepository

def test_question_result_updates_bkt_and_is_idempotent(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "study.db"
    monkeypatch.setattr("config.DB_PATH", db_path); monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    try:
        ApplicationRepository(db_path).initialize()
    except NameError:
        pass
    repo = QuestionRepository(db_path)
    question = {"vignette": "v", "options": ["A) x", "B) y"], "correct": "A", "explanations": {}, "educational_objective": "o", "content_tags": ["AKI"]}
    result = repo.save_pending_questions_batch([{"question": question, "sistema": "Renal", "dificuldade": "Medium"}], request_id="batch1")
    question_id = result.rows[0]["id"]

    assert repo.record_question_result(question_id, "Renal", True, ["AKI"], 20, "Certeza Absoluta") is True
    assert repo.record_question_result(question_id, "Renal", True, ["AKI"], 20, "Certeza Absoluta") is False

    with connection(db_path) as conn:
        row = conn.execute("SELECT correct, total FROM tag_stats WHERE tag = 'AKI'").fetchone()
    assert dict(row) == {"correct": 1, "total": 1}


def test_review_queue_contains_due_cards_and_pending_questions(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "study.db"
    monkeypatch.setattr("config.DB_PATH", db_path); monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    try:
        ApplicationRepository(db_path).initialize()
    except NameError:
        pass
    
    FlashcardRepository(db_path).save_flashcard("Front", "Back", "Renal", ["AKI"])
    question = {"vignette": "v", "options": ["A) x", "B) y"], "correct": "A", "explanations": {}, "educational_objective": "o", "content_tags": ["AKI"]}
    QuestionRepository(db_path).save_pending_questions_batch([{"question": question, "sistema": "Renal", "dificuldade": "Easy"}], request_id="batch2")

    assert len(FlashcardRepository(db_path).get_due_flashcards()) == 1
    assert len(QuestionRepository(db_path).get_pending_questions()) == 1
