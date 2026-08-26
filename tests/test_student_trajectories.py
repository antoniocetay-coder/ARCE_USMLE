from __future__ import annotations

import pytest
from core.algorithms.diffusion_engine import OntologyDiffusionEngine
from core.algorithms.tag_selector import TagSelectionPolicyNetwork


@pytest.fixture
def clinical_graph():
    nodes = [
        "Glomerular Filtration Barrier",
        "Podocytes",
        "Nephritic Syndrome",
        "Poststreptococcal Glomerulonephritis",
        "Proteinuria",
        "Hematuria",
        "Penicillin",
    ]
    edges = [
        {"source": "Podocytes", "relation": "PREREQUISITE_FOR", "target": "Glomerular Filtration Barrier"},
        {"source": "Glomerular Filtration Barrier", "relation": "PREREQUISITE_FOR", "target": "Nephritic Syndrome"},
        {"source": "Nephritic Syndrome", "relation": "MANIFESTS_AS", "target": "Hematuria"},
        {"source": "Nephritic Syndrome", "relation": "MANIFESTS_AS", "target": "Proteinuria"},
        {"source": "Poststreptococcal Glomerulonephritis", "relation": "TREATED_BY", "target": "Penicillin"},
    ]
    return nodes, edges


def test_synthetic_student_root_cause_recovery(clinical_graph):
    nodes, edges = clinical_graph
    engine = OntologyDiffusionEngine(nodes, edges)
    policy = TagSelectionPolicyNetwork(engine)

    # Student repeatedly fails Nephritic Syndrome (mastery 0.15)
    seed_heat = {"Nephritic Syndrome": 1.0}
    mastery_map = {
        "Nephritic Syndrome": 0.15,
        "Glomerular Filtration Barrier": 0.20,
        "Podocytes": 0.25,
        "Hematuria": 0.70,
    }

    selected_tags = policy.select_study_tags(seed_heat, mastery_map, limit=4)
    assert len(selected_tags) > 0

    tag_names = [t["tag"] for t in selected_tags]
    # Asserts that prerequisite root cause "Glomerular Filtration Barrier" is prioritized
    assert "Glomerular Filtration Barrier" in tag_names or "Podocytes" in tag_names
    assert selected_tags[0]["score"] > 0.0


def test_distractor_confusion_trap(clinical_graph):
    nodes, edges = clinical_graph
    confusions = [{"tag_correct": "Nephritic Syndrome", "tag_confused": "Poststreptococcal Glomerulonephritis"}]

    engine = OntologyDiffusionEngine(nodes, edges, confusions=confusions)
    policy = TagSelectionPolicyNetwork(engine)

    seed_heat = {"Nephritic Syndrome": 1.0}
    mastery_map = {"Nephritic Syndrome": 0.30, "Poststreptococcal Glomerulonephritis": 0.25}

    selected_tags = policy.select_study_tags(seed_heat, mastery_map, confusions=confusions, limit=5)
    tag_names = [t["tag"] for t in selected_tags]

    # Asserts that the confused distractor trap is prioritized
    assert "Poststreptococcal Glomerulonephritis" in tag_names
