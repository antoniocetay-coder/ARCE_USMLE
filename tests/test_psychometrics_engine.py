from __future__ import annotations

import pytest
from core.algorithms.psychometrics import PsychometricsEngine, MurphyDecomposition, USMLEContinuousPrediction


def test_murphy_decomposition_empty():
    res = PsychometricsEngine.compute_murphy_and_ece([])
    assert isinstance(res, MurphyDecomposition)
    assert res.brier_score == 0.0
    assert res.n_samples == 0
    assert res.calibration_grade == "Sem dados"


def test_murphy_decomposition_perfect():
    rows = [
        {"confidence_level": "Certeza Absoluta", "answered_correctly": 1},
        {"confidence_level": "Certeza Absoluta", "answered_correctly": 1},
        {"confidence_level": "Certeza Absoluta", "answered_correctly": 1},
        {"confidence_level": "Chute Cego", "answered_correctly": 0},
    ]
    res = PsychometricsEngine.compute_murphy_and_ece(rows)
    assert res.brier_score < 0.10
    assert res.calibration_grade == "Calibração Excepcional 🎯"
    assert res.n_samples == 4


def test_murphy_decomposition_overconfidence():
    rows = [
        {"confidence_level": "Certeza Absoluta", "answered_correctly": 0},
        {"confidence_level": "Certeza Absoluta", "answered_correctly": 0},
        {"confidence_level": "Certeza Absoluta", "answered_correctly": 0},
    ]
    res = PsychometricsEngine.compute_murphy_and_ece(rows)
    assert res.brier_score > 0.80
    assert res.calibration_grade == "Ilusão de Competência 🚨"
    assert res.overconfidence > 0.50


def test_usmle_continuous_prediction():
    system_counts = {
        "General_Principles": 20,
        "Cardiovascular": 15,
        "Renal": 18,
        "Pulmonology": 12,
        "Neurology": 10,
    }
    pred = PsychometricsEngine.predict_usmle(
        total_questions=100,
        correct_questions=80,
        system_counts=system_counts,
        fsrs_retention=0.90,
    )
    assert isinstance(pred, USMLEContinuousPrediction)
    assert pred.step1_pass_prob >= 80.0
    assert 220 <= pred.step2ck_predicted_score <= 270
    assert pred.step2ck_ci_lower <= pred.step2ck_predicted_score <= pred.step2ck_ci_upper
    assert pred.sem > 0


def test_latency_classification():
    z1, s1 = PsychometricsEngine.classify_latency_and_cognition(5.0, False, "Chute Cego")
    assert s1 == "rapid_guess"

    z2, s2 = PsychometricsEngine.classify_latency_and_cognition(35.0, True, "Certeza Absoluta")
    assert s2 == "diagnostic_fluency"

    z3, s3 = PsychometricsEngine.classify_latency_and_cognition(200.0, False, "Dúvida entre 2")
    assert s3 == "cognitive_stalling"
