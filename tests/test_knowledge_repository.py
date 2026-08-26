from __future__ import annotations

import database
from core.repositories.knowledge_repository import KnowledgeRepository
from core.repositories.database import connection

def test_knowledge_repository_save_and_retrieve_node(tmp_path) -> None:
    db_path = tmp_path / "study.db"
    
    import database
    database.DB_PATH = db_path
    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    try:
        ApplicationRepository(db_path).initialize()
    except NameError:
        pass

    repo = KnowledgeRepository(db_path)
    repo.save_node(
        node_id="node_test_gene_123",
        title="BRCA1 gene",
        ontology_type="gene",
        aliases=["BRCA1", "Breast Cancer 1"],
        folder_category="01_Foundations_and_Methods",
        fragments=[
            {
                "fragment_id": "unit_001",
                "source_chunk": "chunk_001",
                "source_lines": "10-20",
                "sha256": "abc123hash",
                "content": "BRCA1 is a tumor suppressor gene involved in DNA repair.",
            }
        ],
    )

    node = repo.get_node_by_id("node_test_gene_123")
    assert node is not None
    assert node.title == "BRCA1 gene"
    assert node.ontology_type == "gene"
    assert "Breast Cancer 1" in node.aliases
    assert len(node.fragments) == 1
    assert "DNA repair" in node.fragments[0].content

    counts = repo.get_ontology_counts()
    assert counts.get("gene") == 1
