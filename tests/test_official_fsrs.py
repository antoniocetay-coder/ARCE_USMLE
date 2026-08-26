from __future__ import annotations

import pytest

from core.algorithms.fsrs import (
    calculate_fsrs,
    calculate_retrievability,
    initialize_difficulty_stability,
)


def test_calculate_retrievability_positive_and_zero_stability() -> None:
    assert calculate_retrievability(0, 5.0) == 1.0
    assert calculate_retrievability(10, 0.0) == 0.0
    assert calculate_retrievability(-1, 0.0) == 0.0
    r = calculate_retrievability(9, 1.0)
    assert 0.0 < r < 1.0


def test_initialize_difficulty_stability() -> None:
    diff, stab = initialize_difficulty_stability(3)
    assert 1.0 <= diff <= 10.0
    assert stab > 0.0


@pytest.mark.parametrize("grade", [1, 2, 3, 4])
def test_calculate_fsrs_all_grades(grade: int) -> None:
    difficulty, stability, retrievability, interval, repetitions, lapses = calculate_fsrs(
        grade=grade,
        difficulty=5.0,
        stability=1.0,
        elapsed_days=1,
        repetitions=1,
        lapses=0,
    )

    assert 1.0 <= difficulty <= 10.0
    assert stability > 0.0
    assert 0.0 <= retrievability <= 1.0
    assert interval >= 1
    assert repetitions >= 1
    assert lapses >= 0


def test_calculate_fsrs_initial_review() -> None:
    difficulty, stability, retrievability, interval, repetitions, lapses = calculate_fsrs(
        grade=3,
        difficulty=5.0,
        stability=1.0,
        elapsed_days=0,
        repetitions=0,
        lapses=0,
    )

    assert 1.0 <= difficulty <= 10.0
    assert stability > 0.0
    assert interval >= 1
    assert repetitions >= 1
