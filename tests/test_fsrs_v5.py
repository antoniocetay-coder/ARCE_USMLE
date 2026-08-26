from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from core.algorithms.fsrs import (
    CardState,
    apply_fuzz,
    calculate_card_preview,
    calculate_fsrs,
    calculate_interval,
    calculate_retrievability,
    format_interval_human,
)
from core.flashcard_service import review_flashcard
from core.repositories.flashcard_repository import FlashcardRepository


def test_calculate_retrievability_properties():
    # t = 0 -> R = 1.0 (100% retention)
    assert calculate_retrievability(0.0, 10.0) == 1.0

    # t = S -> R = 0.90 (90% nominal retention on scheduled due date)
    r_at_s = calculate_retrievability(10.0, 10.0)
    assert pytest.approx(r_at_s, abs=0.01) == 0.90

    # t = 2S -> R < 0.85
    r_at_2s = calculate_retrievability(20.0, 10.0)
    assert r_at_2s < r_at_s
    assert r_at_2s > 0.75


def test_desired_retention_scaling():
    stability = 20.0
    # Higher retention demands shorter intervals (more frequent reviews)
    int_95 = calculate_interval(stability, desired_retention=0.95)
    int_90 = calculate_interval(stability, desired_retention=0.90)
    int_80 = calculate_interval(stability, desired_retention=0.80)

    assert int_95 < int_90 < int_80
    assert pytest.approx(int_90, abs=0.5) == 20.0


def test_smart_fuzzing_boundaries():
    # Short intervals (< 2.5 days) should NOT be perturbed (consolidation stage)
    assert apply_fuzz(1.0, grade=3, seed=42) == 1.0
    assert apply_fuzz(2.0, grade=3, seed=42) == 2.0

    # Longer intervals should have controlled fuzz within +/- 5%
    fuzzed_100 = apply_fuzz(100.0, grade=3, seed=123)
    assert 94.0 <= fuzzed_100 <= 106.0


def test_format_interval_human():
    assert format_interval_human(0.007) == "<10m"
    assert format_interval_human(0.04) == "<1h"
    assert format_interval_human(0.5) == "12h"
    assert format_interval_human(1.0) == "1d"
    assert format_interval_human(5.4) == "5d"
    assert format_interval_human(45.0) == "1.5m"
    assert format_interval_human(400.0) == "1.1a"


def test_calculate_card_preview_new_card():
    new_card = {
        "id": 101,
        "stability": 1.0,
        "difficulty": 5.0,
        "repetitions": 0,
        "lapses": 0,
        "state": CardState.NEW,
    }
    preview = calculate_card_preview(new_card, desired_retention=0.90)

    assert preview.telemetry.state == CardState.NEW
    assert preview.telemetry.repetitions == 0
    assert len(preview.ratings) == 4

    again = preview.ratings[1]
    hard = preview.ratings[2]
    good = preview.ratings[3]
    easy = preview.ratings[4]

    assert again.interval_display == "<10m"
    assert hard.interval_days >= 1.0
    assert good.interval_days >= hard.interval_days
    assert easy.interval_days >= good.interval_days


def test_calculate_card_preview_review_card():
    review_card = {
        "id": 102,
        "stability": 15.0,
        "difficulty": 4.5,
        "repetitions": 3,
        "lapses": 0,
        "state": CardState.REVIEW,
        "last_review_at": (datetime.now(timezone.utc) - timedelta(days=15)).isoformat(),
    }
    preview = calculate_card_preview(review_card, desired_retention=0.90)

    assert pytest.approx(preview.telemetry.current_retrievability, abs=0.02) == 0.90
    assert preview.telemetry.state == CardState.REVIEW

    again = preview.ratings[1]
    hard = preview.ratings[2]
    good = preview.ratings[3]
    easy = preview.ratings[4]

    # Monotonic interval order: Again < Hard < Good <= Easy
    assert again.interval_days < hard.interval_days
    assert hard.interval_days < good.interval_days
    assert good.interval_days <= easy.interval_days

    assert again.new_state == CardState.RELEARNING
    assert good.new_state == CardState.REVIEW


def test_backward_compatible_calculate_fsrs():
    diff, stab, r, interval, reps, lapses = calculate_fsrs(
        grade=3,
        difficulty=5.0,
        stability=10.0,
        elapsed_days=10,
        repetitions=2,
        lapses=0,
        desired_retention=0.90,
    )
    assert 1.0 <= diff <= 10.0
    assert stab > 10.0
    assert pytest.approx(r, abs=0.02) == 0.90
    assert interval >= 10
    assert reps == 3
    assert lapses == 0


def test_review_flashcard_persistence(tmp_path: Path):
    from core.repositories.application_repository import ApplicationRepository

    db_file = tmp_path / "test_fsrs.db"
    ApplicationRepository(db_file).initialize()

    repo = FlashcardRepository(db_file)
    card_dict = repo.save_flashcard(
        front="What receptor is blocked by atropine?",
        back="Muscarinic acetylcholine receptors.",
        system="Pharmacology",
        tags=["Autonomic", "Atropine"],
    )

    # Initial state
    due_cards = repo.get_due_flashcards()
    assert len(due_cards) == 1
    c = due_cards[0]

    # Calculate preview and review with Good (grade 3)
    preview = calculate_card_preview(c, desired_retention=0.90)
    good_rating = preview.ratings[3]

    interval = review_flashcard(c, grade=3, rating_preview=good_rating)
    assert interval == max(1, round(good_rating.interval_days))
    assert c["repetitions"] == 1
    assert c["stability"] == good_rating.new_stability
    assert c["difficulty"] == good_rating.new_difficulty
    assert c["state"] == int(CardState.REVIEW)
