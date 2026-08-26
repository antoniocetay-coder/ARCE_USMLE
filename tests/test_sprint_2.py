from __future__ import annotations

import json
from datetime import datetime, timezone

import database
from core.ai.ai_cache import compute_prompt_hash, get_cached_response, store_cached_response
from core.ai.isomorphic_generator import construir_prompt_isomorfico
from core.algorithms.discrimination_drill import DiscriminationDrillService
from core.algorithms.scheduler import create_study_queue
from core.repositories.application_repository import ApplicationRepository
from core.services.dashboard_service import DashboardService


def test_sprint2_schema_migrations_and_indexes(tmp_path, monkeypatch):
    db_path = tmp_path / "sprint2_test.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    ApplicationRepository(db_path).initialize()

    with database.get_conn() as conn:
        tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "ai_response_cache" in tables
        assert "isomorphic_vignettes" in tables

        indexes = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
        assert "idx_questions_status_system" in indexes
        assert "idx_srs_state_due_type" in indexes
        assert "idx_ontology_edges_rel_target" in indexes


def test_sprint2_ai_response_cache(tmp_path, monkeypatch):
    db_path = tmp_path / "cache_test.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    ApplicationRepository(db_path).initialize()

    prompt = "Why does FeNa stay < 1% in Pre-Renal Azotemia?"
    model = "gemini-3.5-flash"
    response = "Tubular epithelial cells are intact and retain full sodium reabsorption capacity."

    # Cache should be empty initially
    assert get_cached_response(prompt, model, db_path) is None

    # Store in cache
    store_cached_response(prompt, model, response, db_path)

    # Retrieval should hit cache
    cached = get_cached_response(prompt, model, db_path)
    assert cached == response


def test_sprint2_discrimination_drills_service(tmp_path, monkeypatch):
    db_path = tmp_path / "drills_test.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    ApplicationRepository(db_path).initialize()

    service = DiscriminationDrillService(db_path)
    drills = service.get_drills(limit=5)
    assert len(drills) == 5
    first = drills[0]
    assert first.concept_a != ""
    assert first.concept_b != ""
    assert first.correct_choice in ("A", "B")
    assert first.prompt_clue != ""
    assert first.pivot_explanation != ""


def test_sprint2_dashboard_service_drills_and_interleaved_queue(tmp_path, monkeypatch):
    db_path = tmp_path / "dashboard_sprint2.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    database.init_db()
    ApplicationRepository(db_path).initialize()

    dashboard = DashboardService()
    
    # Drills Mode
    drill_queue = dashboard.create_queue("Drills")
    assert isinstance(drill_queue, list)
    assert len(drill_queue) >= 1
    assert drill_queue[0]["type"] == "drill"
    assert "concept_a" in drill_queue[0]["item"]

    # Interleaved Mode
    inter_queue = dashboard.create_queue("Interleaved")
    assert isinstance(inter_queue, list)


def test_sprint2_isomorphic_prompt_contracts():
    prompt = construir_prompt_isomorfico(
        original_vignette="A 60-year-old male with acute back pain...",
        objective="Recognize abdominal aortic aneurysm rupture.",
        correct_opt="C",
        correct_exp="Pulsatile abdominal mass and hypotension represent ruptured AAA.",
        options=["A) Kidney stone", "B) Appendicitis", "C) Ruptured AAA", "D) Diverticulitis", "E) Cholecystitis"]
    )
    assert "ISOMORPHIC TRANSFER VIGNETTE" in prompt
    assert "DIFFERENT SUPERFICIAL SURFACE FEATURES" in prompt
    assert "SAME COGNITIVE DEPTH" in prompt
