from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.ai.validators import validate_question
from core.models.study_session import StudyQueueItem, StudySession
from core.repositories.question_repository import QuestionRepository


def question_payload() -> dict:
    return {
        "vignette": "A patient presents with a classic finding.",
        "options": ["A) Diagnosis A", "B) Diagnosis B", "C) Diagnosis C", "D) Diagnosis D", "E) Diagnosis E"],
        "correct": "A",
        "explanations": {letter: f"Explanation {letter}" for letter in "ABCDE"},
        "educational_objective": "Recognize the classic finding.",
        "content_tags": ["Tag"],
        "distractor_tags": {letter: "Tag" for letter in "ABCDE"},
        "difficulty": "Medium",
        "cognitive_order": "2nd Order",
    }


def test_valid_question_is_accepted() -> None:
    result = validate_question(question_payload(), "System", valid_tags={"Tag"})
    assert result.is_valid
    assert result.errors == []


@pytest.mark.parametrize("field,value", [("correct", "Z"), ("content_tags", ["Unknown"])])
def test_invalid_question_is_rejected(field: str, value: object) -> None:
    payload = question_payload()
    payload[field] = value
    assert not validate_question(payload, "System", valid_tags={"Tag"}).is_valid


def test_queue_appends_generated_card_and_requeues_again_with_limit() -> None:
    session = StudySession(mode="plan")
    question = StudyQueueItem("question", "q-1", "initial", {"id": 1})
    card = StudyQueueItem("flashcard", "f-1", "generated", {"id": 2})
    session.append_item(question)
    session.append_item(card)
    assert session.current_item == question
    session.advance()
    assert session.current_item == card
    for _ in range(3):
        assert session.requeue_item(card, "Again")
        session.advance()
    assert not session.requeue_item(card, "Again")
    session.advance()
    assert session.remaining_count() == 0


def test_end_clears_only_session_state() -> None:
    session = StudySession(mode="plan")
    session.append_item(StudyQueueItem("question", "q-1", "initial", {"id": 1}))
    session.selected_answer = "A"
    session.answer_submitted = True
    session.end()
    assert session.mode is None
    assert session.remaining_count() == 0
    assert session.selected_answer is None


def test_question_batch_is_atomic_and_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "test.db"
    repository = QuestionRepository(database)
    repository.initialize_schema()
    entries = [{"sistema": "System", "dificuldade": "Medium", "question": question_payload()}]
    first = repository.save_pending_questions_batch(entries, request_id="request-1")
    second = repository.save_pending_questions_batch(entries, request_id="request-1")
    assert len(first.rows) == 1
    assert second.duplicate
    assert len(repository.get_pending_questions()) == 1
    with pytest.raises(KeyError):
        repository.save_pending_questions_batch([{"sistema": "System"}], request_id="request-2")
    assert len(repository.get_pending_questions()) == 1


def test_architecture_boundaries_and_no_streamlit() -> None:
    root = Path(__file__).parents[1]
    for path in (root / "core" / "algorithms").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)}
        assert "sqlite3" not in names
        assert "nicegui" not in names
    assert not list(root.rglob("*streamlit*"))
    for path in (root / "pages").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        assert "sqlite3" not in imports
        assert not any(isinstance(node, ast.Attribute) and node.attr == "execute" for node in ast.walk(tree))


def test_legacy_root_modules_are_migrated() -> None:
    root = Path(__file__).parents[1]
    for name in ("scheduler.py", "analytics.py", "mastery.py", "fsrs.py", "ai_engine.py", "validation.py"):
        assert not (root / name).exists(), f"legacy root module remains: {name}"
