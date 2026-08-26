from __future__ import annotations

import pytest
from core.repositories.knowledge_repository import KnowledgeRepository
from core.services.ontology_vault_service import OntologyVaultService
from database import init_db


@pytest.fixture(autouse=True)
def setup_vault_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_vault.db"
    import database
    monkeypatch.setattr(database, "DB_PATH", db_file)
    init_db()
    repo = KnowledgeRepository(path=db_file)
    repo.save_node("node_gfr", "GFR", "concept", ["Glomerular Filtration Rate"], "Renal", [{"fragment_id": "f1", "content": "GFR content"}])
    repo.save_node("node_stemi", "STEMI", "disease", ["Myocardial Infarction"], "Cardiovascular", [{"fragment_id": "f2", "content": "STEMI content"}])
    return db_file


def test_get_vault_categories(setup_vault_db):
    service = OntologyVaultService(KnowledgeRepository(path=setup_vault_db))
    categories = service.get_vault_categories()
    assert "Renal" in categories or "Cardiovascular" in categories


def test_list_nodes_in_category(setup_vault_db):
    repo = KnowledgeRepository(path=setup_vault_db)
    service = OntologyVaultService(repo)
    nodes = service.list_nodes_in_category("Renal")
    assert len(nodes) >= 1
    assert nodes[0].title == "GFR"


def test_resolve_tag_to_node(setup_vault_db):
    repo = KnowledgeRepository(path=setup_vault_db)
    service = OntologyVaultService(repo)
    node = service.resolve_tag_to_node("STEMI")
    assert node is not None
    assert node.node_id == "node_stemi"
