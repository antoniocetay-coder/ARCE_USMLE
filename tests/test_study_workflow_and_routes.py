from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest

import database
from config import DB_PATH
from core.flashcard_service import review_flashcard
from core.repositories.application_repository import ApplicationRepository
from core.repositories.flashcard_repository import FlashcardRepository
from core.repositories.question_repository import QuestionRepository
from core.services.dashboard_service import DashboardService
from core.services.study_service import StudyService
from core.services.study_workflow_service import StudyWorkflowService
from pages.study import sanitize_session_queue
from state.study_session import StudySession


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_arce.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    ApplicationRepository(db_path).initialize()
    return db_path


def test_review_flashcard_updates_sqlite_and_card_dict(test_db):
    repo = FlashcardRepository(test_db)
    saved = repo.save_flashcard("Question Front", "Answer Back", "Renal", ["Renal", "FeNa"])
    card_id = saved["id"]

    # Initial state verification
    due_cards = repo.get_due_flashcards()
    assert any(c["id"] == card_id for c in due_cards)

    card_dict = {
        "id": card_id,
        "front": "Question Front",
        "back": "Answer Back",
        "sistema": "Renal",
        # FSRS fields missing or default
    }

    interval = review_flashcard(card_dict, 3)  # Good
    assert interval >= 1
    assert card_dict["repetitions"] == 1
    assert card_dict["stability"] > 0
    assert "last_review" in card_dict
    assert "due" in card_dict

    # Check database persistence
    with database.get_conn() as conn:
        row = conn.execute("SELECT * FROM srs_state WHERE object_id = ? AND object_type = 'flashcard'", (card_id,)).fetchone()
        assert row is not None
        assert row["repetitions"] == 1
        assert row["stability"] > 0


def test_save_flashcards_to_session_produces_valid_structure(test_db):
    session = StudySession(mode="QBank")
    workflow = StudyWorkflowService()

    drafts = [
        ("Front concept 1", "Back answer 1", ["Cardio", "STEMI"]),
        ("Front concept 2", "Back answer 2", ["Cardio", "ECG"]),
    ]

    saved_count = workflow.save_flashcards_to_session(session, drafts, "Cardiovascular")
    assert saved_count == 2
    assert len(session.queue) == 2

    first_item = session.queue[0]
    assert first_item["type"] == "flashcard"
    assert isinstance(first_item["item"]["id"], int)
    assert first_item["item"]["front"] == "Front concept 1"
    assert first_item["item"]["difficulty"] == 5.0

    # Test review of this newly saved flashcard directly from queue
    interval = review_flashcard(first_item["item"], 4)  # Easy
    assert interval >= 1
    assert first_item["item"]["repetitions"] == 1


def test_sanitize_session_queue_removes_deleted_questions(test_db):
    q_repo = QuestionRepository(test_db)
    question = {"vignette": "v1", "options": ["A) 1", "B) 2"], "correct": "A", "explanations": {}, "content_tags": ["Tag1"]}
    saved_batch = q_repo.save_pending_questions_batch([{"question": question, "sistema": "Renal", "dificuldade": "Easy"}], request_id="b1")
    valid_id = saved_batch.rows[0]["id"]

    session = StudySession(
        mode="QBank",
        queue=[
            {"type": "question", "item": {"id": valid_id, "sistema": "Renal"}},
            {"type": "question", "item": {"id": 999999, "sistema": "Renal"}},  # Non-existent ID
            {"type": "flashcard", "item": {"id": 1, "front": "F", "back": "B"}},
        ],
    )

    modified = sanitize_session_queue(session)
    assert modified is True
    assert len(session.queue) == 2
    assert session.queue[0]["item"]["id"] == valid_id
    assert session.queue[1]["type"] == "flashcard"


def test_error_retest_queue_and_submission(test_db):
    q_repo = QuestionRepository(test_db)
    q_data = {"vignette": "Incorrect vignette", "options": ["A) Wrong", "B) Right"], "correct": "B", "explanations": {}, "content_tags": ["Cardio"]}
    batch = q_repo.save_pending_questions_batch([{"question": q_data, "sistema": "Cardiovascular", "dificuldade": "Hard"}], request_id="batch_err")
    qid = batch.rows[0]["id"]

    # First record as answered incorrectly
    q_repo.record_question_result(qid, "Cardiovascular", False, ["Cardio"], 45, "Chute Cego")

    # Verify get_incorrect_questions finds it
    incorrect = q_repo.get_incorrect_questions()
    assert any(q["id"] == qid for q in incorrect)

    # Re-test preparation
    restudy = q_repo.prepare_incorrect_for_restudy(limit=10)
    assert any(q["id"] == qid and q["status"] == "pending" for q in restudy)

    # Put into session and submit correct answer
    queue_rows = [{"id": q["id"], "sistema": q["sistema"], "dificuldade": q["dificuldade"], "question_json": json.dumps(q)} for q in restudy]
    session = StudySession(mode="Caderno de Erros", queue=[{"type": "question", "item": queue_rows[0]}])

    service = StudyService(repository=q_repo)
    result = service.submit_answer(session, "B", "Certeza Absoluta", 0, 30)
    assert result.is_correct is True
    assert result.persisted is True


def test_dashboard_service_create_queue_modes(test_db):
    dashboard = DashboardService()
    # Caderno de erros mode
    err_queue = dashboard.create_queue("Caderno de Erros")
    assert isinstance(err_queue, list)

    # Review mode
    rev_queue = dashboard.create_queue("Review")
    assert isinstance(rev_queue, list)

    # QBank mode
    qbank_queue = dashboard.create_queue("QBank")
    assert isinstance(qbank_queue, list)

    # Interleaved mode
    inter_queue = dashboard.create_queue("Interleaved")
    assert isinstance(inter_queue, list)


def test_dashboard_caderno_de_erros_queue_direct_submission(test_db):
    q_repo = QuestionRepository(test_db)
    q_data = {
        "vignette": "Direct error test vignette",
        "options": ["A) Choice A", "B) Choice B", "C) Choice C"],
        "correct": "C",
        "explanations": {"A": "No", "B": "No", "C": "Yes"},
        "content_tags": ["Renal"],
    }
    batch = q_repo.save_pending_questions_batch(
        [{"question": q_data, "sistema": "Renal", "dificuldade": "Medium"}],
        request_id="batch_caderno_direct",
    )
    qid = batch.rows[0]["id"]
    # Mark incorrect
    q_repo.record_question_result(qid, "Renal", False, ["Renal"], 25, "Chute Cego")

    # Generate queue via DashboardService
    dashboard = DashboardService()
    queue = dashboard.create_queue("Caderno de Erros")
    assert len(queue) >= 1
    first_item = queue[0]
    assert first_item["type"] == "question"
    assert "question_json" in first_item["item"]

    # Submit directly using StudyService
    session = StudySession(mode="Caderno de Erros", queue=queue)
    service = StudyService(repository=q_repo)
    result = service.submit_answer(session, "C", "Certeza Absoluta", 0, 15)
    assert result.is_correct is True
    assert result.persisted is True
    assert session.answer_submitted is True
    assert session.is_correct is True


def test_study_flashcard_deletion_does_not_skip_subsequent_cards(test_db):
    repo = FlashcardRepository(test_db)
    c1 = repo.save_flashcard("Card 1 Front", "Card 1 Back", "Renal", ["Renal"])
    c2 = repo.save_flashcard("Card 2 Front", "Card 2 Back", "Cardio", ["Cardio"])
    c3 = repo.save_flashcard("Card 3 Front", "Card 3 Back", "Neuro", ["Neuro"])

    session = StudySession(
        mode="Review",
        queue=[
            {"type": "flashcard", "item": {"id": c1["id"], "front": "Card 1 Front", "back": "Card 1 Back"}},
            {"type": "flashcard", "item": {"id": c2["id"], "front": "Card 2 Front", "back": "Card 2 Back"}},
            {"type": "flashcard", "item": {"id": c3["id"], "front": "Card 3 Front", "back": "Card 3 Back"}},
        ],
        current_index=0,
    )

    # Delete card 1
    card_to_delete = session.current_item
    assert card_to_delete["item"]["id"] == c1["id"]

    repo.delete_flashcard(card_to_delete["item"]["id"])
    if 0 <= session.current_index < len(session.queue):
        session.queue.pop(session.current_index)

    # Now the current item at index 0 MUST be Card 2 (NOT skipped!)
    assert len(session.queue) == 2
    assert session.current_item["item"]["id"] == c2["id"]
    assert session.current_item["item"]["front"] == "Card 2 Front"


def test_analytics_repository_default_instantiation(test_db):
    from core.repositories.analytics_repository import AnalyticsRepository
    repo = AnalyticsRepository()
    assert repo.path is not None
    system_stats = repo.get_system_stats()
    assert isinstance(system_stats, list)
    streak_data = repo.get_user_streak_data()
    assert "streak" in streak_data
    assert "week_dots" in streak_data


def test_study_submit_answer_handles_unserialized_dict_payload(test_db):
    q_repo = QuestionRepository(test_db)
    q_data = {
        "id": 999,
        "vignette": "Unserialized vignette test",
        "options": ["A) Opt 1", "B) Opt 2"],
        "correct": "A",
        "explanations": {"A": "Yes"},
        "content_tags": ["Cardio"],
        "sistema": "Cardiovascular",
        "dificuldade": "Easy",
    }
    # Direct dict without "question_json" key
    session = StudySession(mode="QBank", queue=[{"type": "question", "item": q_data}])
    service = StudyService(repository=q_repo)
    # Even if not in db, submit_answer should not crash on KeyError
    result = service.submit_answer(session, "A", "Certeza Absoluta", 0, 10)
    assert result.is_correct is True
    assert session.answer_submitted is True
    assert session.is_correct is True


def test_knowledge_repository_search_and_resolve_node(test_db):
    from core.repositories.knowledge_repository import KnowledgeRepository
    repo = KnowledgeRepository(test_db)
    repo.save_node(
        node_id="NODE-TEST-01",
        title="Acute Coronary Syndrome",
        ontology_type="Disease",
        aliases=["ACS", "Coronary Syndrome"],
        folder_category="Cardiovascular",
        fragments=[{"fragment_id": "f1", "source_chunk": "Note", "content": "ACS is an emergency."}],
    )

    found = repo.search_nodes("Acute Coronary", limit=5)
    assert len(found) >= 1
    assert found[0].node_id == "NODE-TEST-01"

    found_alias = repo.search_nodes("ACS", limit=5)
    assert len(found_alias) >= 1
    assert found_alias[0].node_id == "NODE-TEST-01"


def test_all_repositories_instantiate_with_dynamic_path(test_db):
    from core.repositories.knowledge_repository import KnowledgeRepository
    from core.repositories.mnemonic_repository import MnemonicRepository
    from core.repositories.pearl_repository import PearlRepository
    from core.repositories.ai_settings_repository import AISettingsRepository
    from core.repositories.flashcard_repository import FlashcardRepository
    from core.repositories.question_repository import QuestionRepository
    from core.repositories.analytics_repository import AnalyticsRepository
    from core.services.flashcard_service import FlashcardService
    from core.services.question_service import QuestionGenerationService

    k_repo = KnowledgeRepository()
    assert k_repo.path == test_db
    m_repo = MnemonicRepository()
    assert m_repo.path == test_db
    p_repo = PearlRepository()
    assert p_repo.path == test_db
    ai_repo = AISettingsRepository()
    assert ai_repo.path == test_db
    f_repo = FlashcardRepository()
    assert f_repo.path == test_db
    q_repo = QuestionRepository()
    assert q_repo.path == test_db
    a_repo = AnalyticsRepository()
    assert a_repo.path == test_db
    f_srv = FlashcardService()
    assert f_srv.repository.path == test_db
    q_srv = QuestionGenerationService()
    assert q_srv.repository.path == test_db


def test_mnemonic_and_pearl_repositories_crud(test_db):
    from core.repositories.mnemonic_repository import MnemonicRepository
    from core.repositories.pearl_repository import PearlRepository

    m_repo = MnemonicRepository()
    m_id = m_repo.salvar_mnemonico("MUDPILES", "M = Methanol, U = Uremia...", "Renal", structured_data='{"anchor": "Acidosis"}')
    assert isinstance(m_id, int)
    mnemonics = m_repo.get_todos_mnemonicos()
    assert any(m["id"] == m_id and m["title"] == "MUDPILES" for m in mnemonics)

    m_repo.atualizar_mnemonico(m_id, "MUDPILES (Updated)", "Updated content", structured_data='{"anchor": "Acidosis 2"}')
    updated = m_repo.get_todos_mnemonicos()
    assert any(m["id"] == m_id and m["title"] == "MUDPILES (Updated)" for m in updated)

    m_repo.deletar_mnemonico(m_id)
    after_del = m_repo.get_todos_mnemonicos()
    assert not any(m["id"] == m_id for m in after_del)

    p_repo = PearlRepository()
    p_id = p_repo.salvar_perola("Na cetoacidose a acidose e anion gap elevado.", "Endocrine")
    assert isinstance(p_id, int)
    pearls = p_repo.get_todas_perolas()
    assert any(p["id"] == p_id and "cetoacidose" in p["pearl_text"] for p in pearls)


def test_dashboard_study_plans_generation(test_db):
    dashboard = DashboardService()
    plans = dashboard.study_plans()
    assert len(plans) == 3
    for p in plans:
        assert "titulo" in p
        assert "sistemas" in p
        assert "tags" in p
        assert len(p["tags"]) >= 1
        assert p["quantity"] == 5


def test_knowledge_card_helpers():
    from components.knowledge_card import clean_snippet, get_ontology_badge_class

    assert get_ontology_badge_class("Disease") == "ontology-badge-disease"
    assert get_ontology_badge_class("Drug_Substance") == "ontology-badge-drug"
    assert get_ontology_badge_class("Gene_Locus") == "ontology-badge-gene"
    assert get_ontology_badge_class("Pathology_Finding") == "ontology-badge-finding"
    assert get_ontology_badge_class("Diagnostic_Test") == "ontology-badge-test"
    assert get_ontology_badge_class("Receptor") == "ontology-badge-receptor"
    assert get_ontology_badge_class("Biological_Pathway") == "ontology-badge-pathway"
    assert get_ontology_badge_class("Other") == "ontology-badge-default"

    raw = "<!-- comment --># Header\n! Alert\n_Source: textbook_;\nNormal line\n\n\nAnother line"
    cleaned = clean_snippet(raw)
    assert "<!--" not in cleaned
    assert "#" not in cleaned
    assert "_Source:" not in cleaned
    assert "Normal line" in cleaned


def test_delete_card_boundary_behavior(test_db):
    repo = FlashcardRepository(test_db)
    c1 = repo.save_flashcard("Card A", "Back A", "Renal", ["Renal"])

    # 1. Single card queue
    session1 = StudySession(mode="Review", queue=[{"type": "flashcard", "item": {"id": c1["id"], "front": "Card A"}}], current_index=0)
    repo.delete_flashcard(c1["id"])
    if 0 <= session1.current_index < len(session1.queue):
        session1.queue.pop(session1.current_index)
    assert len(session1.queue) == 0
    assert session1.current_item is None

    # 2. Deleting last card of 2-card queue
    c2 = repo.save_flashcard("Card B", "Back B", "Cardio", ["Cardio"])
    session2 = StudySession(
        mode="Review",
        queue=[
            {"type": "flashcard", "item": {"id": c1["id"], "front": "Card A"}},
            {"type": "flashcard", "item": {"id": c2["id"], "front": "Card B"}},
        ],
        current_index=1,  # at last item
    )
    repo.delete_flashcard(c2["id"])
    if 0 <= session2.current_index < len(session2.queue):
        session2.queue.pop(session2.current_index)
    assert len(session2.queue) == 1
    assert session2.current_item is None  # index 1 is now beyond length 1


def test_save_flashcards_filters_blank_entries(test_db):
    session = StudySession(mode="Review", queue=[])
    workflow = StudyWorkflowService()
    drafts = [
        ("Valid front", "Valid back", ["Renal"]),
        ("", "No front back", ["Renal"]),
        ("No back front", "   ", ["Renal"]),
        ("   ", "   ", ["Renal"]),
        ("Another valid front", "Another valid back", ["Cardio"]),
    ]
    saved = workflow.save_flashcards_to_session(session, drafts, "Renal")
    assert saved == 2
    assert len(session.queue) == 2
    assert session.queue[0]["item"]["front"] == "Valid front"
    assert session.queue[1]["item"]["front"] == "Another valid front"


def test_review_flashcard_safe_without_id(test_db):
    in_memory_card = {
        "id": None,
        "front": "Front text",
        "back": "Back text",
        "difficulty": 5.0,
        "stability": 1.0,
        "repetitions": 0,
        "lapses": 0,
    }
    interval = review_flashcard(in_memory_card, 3)
    assert interval >= 1
    assert in_memory_card["repetitions"] == 1
    assert in_memory_card["stability"] > 0


def test_ai_configuration_desired_retention_schema_and_migration(tmp_path, monkeypatch):
    custom_db = tmp_path / "migration_test.db"
    monkeypatch.setattr("config.DB_PATH", custom_db)
    monkeypatch.setattr("database.DB_PATH", custom_db)
    database.init_db()

    with database.get_conn() as conn:
        cols_ai = [r["name"] for r in conn.execute("PRAGMA table_info(ai_configuration)").fetchall()]
        assert "desired_retention" in cols_ai
        cols_mn = [r["name"] for r in conn.execute("PRAGMA table_info(mnemonics)").fetchall()]
        assert "structured_data" in cols_mn


def test_ontology_brain_caching_per_repository(test_db, tmp_path):
    from core.repositories.knowledge_repository import KnowledgeRepository
    from core.algorithms.ontology_brain import OntologyBrain

    repo1 = KnowledgeRepository(test_db)
    brain1 = OntologyBrain(repo1)
    rec1 = brain1.recommend_study_tags({"Renal": 0.3})
    assert isinstance(rec1, list)

    db2 = tmp_path / "second.db"
    repo2 = KnowledgeRepository(db2)
    brain2 = OntologyBrain(repo2)
    rec2 = brain2.recommend_study_tags({"Cardio": 0.2})
    assert isinstance(rec2, list)


def test_sanitize_card_list_preserves_all_valid_cards():
    from core.ai.flashcard_generator import sanitize_card_list, parse_flashcards_response

    many_cards = [
        {"front": f"Question {i}", "back": f"Answer {i}", "tags": ["Tag"]}
        for i in range(15)
    ]
    sanitized = sanitize_card_list(many_cards)
    assert len(sanitized) == 15
    assert sanitized[0]["front"] == "Question 0"
    assert sanitized[9]["front"] == "Question 9"

    json_payload = json.dumps({"cards": many_cards})
    parsed = parse_flashcards_response(json_payload)
    assert len(parsed) == 15


def test_flashcard_prompt_analytical_contracts():
    from core.ai.flashcard_prompts import construir_prompt_analitico

    prompt = construir_prompt_analitico(
        vignette="A 45-year-old male presents with acute flank pain...",
        objective="Distinguish Pre-renal AKI from Acute Tubular Necrosis.",
        correct="B",
        correct_explanation="FeNa < 1% indicates intact tubular function in pre-renal state.",
        selected="D",
        selected_explanation="NTA usually presents with FeNa > 2%.",
        context="EXISTING FLASHCARDS: none.",
    )
    assert "MICRO-ATOMIC FLASHCARDS" in prompt
    assert "FLASHCARD HYGIENE RULES" in prompt
    assert "MINIMUM INFORMATION PRINCIPLE" in prompt





