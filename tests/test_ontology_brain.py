from __future__ import annotations

import pytest
from core.algorithms.ontology_brain import OntologyBrain
from database import init_db, seed_ontology_if_empty


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_ontology.db"
    import database
    monkeypatch.setattr(database, "DB_PATH", db_file)
    init_db()
    with database.closing(database.get_conn()) as conn:
        conn.execute("INSERT INTO ontology_edges(source, relation, target) VALUES ('Renin', 'PREREQUISITE_FOR', 'Angiotensin II')")
        conn.execute("INSERT INTO ontology_edges(source, relation, target) VALUES ('Angiotensin II', 'PREREQUISITE_FOR', 'Aldosterone')")
        conn.execute("INSERT INTO ontology_edges(source, relation, target) VALUES ('Aldosterone', 'CAUSES', 'Metabolic Alkalosis')")
        conn.commit()
    return db_file


from core.repositories.knowledge_repository import KnowledgeRepository


def test_ontology_brain_get_prerequisites(tmp_path, setup_db):
    repo = KnowledgeRepository(path=setup_db)
    brain = OntologyBrain(repository=repo)
    prereqs = brain.get_prerequisites("Aldosterone", max_depth=2)
    assert "Angiotensin II" in prereqs
    assert "Renin" in prereqs


def test_ontology_brain_get_clinical_relations(setup_db):
    repo = KnowledgeRepository(path=setup_db)
    brain = OntologyBrain(repository=repo)
    relations = brain.get_clinical_relations("Angiotensin II")
    assert "Renin" in relations["PREREQUISITE_FOR"] or "Aldosterone" in relations["PREREQUISITE_FOR"]


def test_ontology_brain_root_cause_tags(setup_db):
    repo = KnowledgeRepository(path=setup_db)
    brain = OntologyBrain(repository=repo)
    mastery_map = {
        "Aldosterone": 0.20,
        "Angiotensin II": 0.30,
        "Renin": 0.80,
    }
    root_causes = brain.get_root_cause_tags(mastery_map, threshold=0.50)
    assert len(root_causes) > 0
    failing_topics = [rc["failing_topic"] for rc in root_causes]
    assert "Aldosterone" in failing_topics


def test_ontology_brain_recommend_study_tags(setup_db):
    repo = KnowledgeRepository(path=setup_db)
    brain = OntologyBrain(repository=repo)
    mastery_map = {
        "Aldosterone": 0.20,
        "Angiotensin II": 0.30,
    }
    confusions = [{"tag_correct": "Aldosterone", "tag_confused": "Cortisol"}]
    recommendations = brain.recommend_study_tags(mastery_map, confusions, limit=5)
    assert len(recommendations) > 0
    tags = [r["tag"] for r in recommendations]
    assert "Angiotensin II" in tags or "Cortisol" in tags or "Aldosterone" in tags
