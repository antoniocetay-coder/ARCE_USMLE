from __future__ import annotations

from core.ai.rag_service import RAGService
from core.repositories.knowledge_repository import KnowledgeRepository
from core.repositories.database import connection

def test_rag_service_retrieves_context_for_target_terms(tmp_path) -> None:
    db_path = tmp_path / "study.db"
    
    # Init DB schema
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
        node_id="node_myasthenia_gravis_001",
        title="Myasthenia gravis",
        ontology_type="disease",
        aliases=["MG", "Myasthenia"],
        folder_category="04_Processes_and_Pathology",
        fragments=[
            {
                "fragment_id": "unit_mg_001",
                "source_chunk": "chunk_010",
                "source_lines": "100-110",
                "sha256": "hash_mg_123",
                "content": "Autoantibodies against postsynaptic ACh receptors leading to muscle weakness worsening with use.",
            }
        ],
    )

    rag = RAGService(repo)
    context = rag.search_knowledge_context(["Myasthenia gravis"], limit=3)
    assert "Myasthenia gravis" in context
    assert "postsynaptic ACh receptors" in context
