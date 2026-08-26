from __future__ import annotations

import pytest
from core.algorithms.diffusion_engine import OntologyDiffusionEngine


@pytest.fixture
def sample_graph_data():
    nodes = ["Renin", "Angiotensin II", "Aldosterone", "Metabolic Alkalosis", "Isolated Orphan Node"]
    edges = [
        {"source": "Renin", "relation": "PREREQUISITE_FOR", "target": "Angiotensin II"},
        {"source": "Angiotensin II", "relation": "PREREQUISITE_FOR", "target": "Aldosterone"},
        {"source": "Aldosterone", "relation": "CAUSES", "target": "Metabolic Alkalosis"},
    ]
    return nodes, edges


def test_energy_conservation_and_convergence(sample_graph_data):
    nodes, edges = sample_graph_data
    engine = OntologyDiffusionEngine(nodes, edges)

    seed_heat = {"Aldosterone": 1.0}
    heat_result = engine.diffuse(seed_heat, steps=3, alpha=0.70)

    # Asserts that heat on all nodes is strictly bounded in [0.0, 1.0] and does not diverge
    for tag, heat in heat_result.items():
        assert 0.0 <= heat <= 1.0, f"Heat on '{tag}' diverged: {heat}"


def test_directional_weight_asymmetry(sample_graph_data):
    nodes, edges = sample_graph_data
    engine = OntologyDiffusionEngine(nodes, edges)

    # Ingest heat on Aldosterone (target of PREREQUISITE_FOR Angiotensin II, source of CAUSES Metabolic Alkalosis)
    seed_heat = {"Aldosterone": 1.0}
    heat_result = engine.diffuse(seed_heat, steps=1, alpha=0.80)

    # PREREQUISITE_FOR backwards weight is 0.85, whereas CAUSES forward weight is 0.60
    prereq_heat = heat_result.get("Angiotensin II", 0.0)
    causes_heat = heat_result.get("Metabolic Alkalosis", 0.0)

    assert prereq_heat > 0.0, "Prerequisite 'Angiotensin II' did not receive heat"
    assert causes_heat > 0.0, "Cause 'Metabolic Alkalosis' did not receive heat"
    assert prereq_heat > causes_heat, f"Prerequisite heat ({prereq_heat}) should be greater than causes heat ({causes_heat})"


def test_orphan_node_isolation(sample_graph_data):
    nodes, edges = sample_graph_data
    engine = OntologyDiffusionEngine(nodes, edges)

    seed_heat = {"Renin": 1.0}
    heat_result = engine.diffuse(seed_heat, steps=3, alpha=0.70)

    # Isolated Orphan Node should receive zero heat leakage
    orphan_heat = heat_result.get("Isolated Orphan Node", 0.0)
    assert orphan_heat == 0.0, f"Orphan node received leaked heat: {orphan_heat}"
