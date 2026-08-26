from __future__ import annotations

from typing import Any

import config
from core.repositories.database import connection
from core.repositories.knowledge_repository import KnowledgeNodeData, KnowledgeRepository


class OntologyVaultService:
    """Serviço de acesso à Ontologia oficial baseada nos 8.046 Nós Médicos do Obsidian Vault."""

    def __init__(self, repository: KnowledgeRepository | None = None) -> None:
        self.repository = repository or KnowledgeRepository(config.DB_PATH)

    def get_vault_categories(self) -> list[str]:
        """Retorna todas as categorias de pastas extraídas das páginas .md do Obsidian."""
        with connection(self.repository.path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT folder_category FROM knowledge_nodes WHERE folder_category IS NOT NULL AND folder_category != '' ORDER BY folder_category"
            ).fetchall()
            categories = [r["folder_category"] for r in rows]
            return categories if categories else ["General_Principles", "Renal", "Cardiovascular"]

    def get_all_ontology_types(self) -> list[str]:
        """Retorna todos os tipos ontológicos dos nós (ex.: disease, drug, anatomy, etc.)."""
        with connection(self.repository.path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT ontology_type FROM knowledge_nodes WHERE ontology_type IS NOT NULL AND ontology_type != '' ORDER BY ontology_type"
            ).fetchall()
            types = [r["ontology_type"] for r in rows]
            return types

    def list_nodes_in_category(self, category: str, limit: int = 50) -> list[KnowledgeNodeData]:
        """Lista os nós médicos pertencentes a uma categoria específica do Vault."""
        with connection(self.repository.path) as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge_nodes WHERE folder_category = ? ORDER BY title LIMIT ?",
                (category, limit),
            ).fetchall()
            return [
                KnowledgeNodeData(
                    node_id=r["node_id"],
                    title=r["title"],
                    ontology_type=r["ontology_type"],
                    aliases=[],
                    folder_category=r["folder_category"],
                    fragments=[],
                )
                for r in rows
            ]

    def resolve_tag_to_node(self, tag: str) -> KnowledgeNodeData | None:
        """Resolve uma string de tag genérica para o nó correspondente do Obsidian Vault."""
        tag_clean = tag.strip().replace("_", " ")
        nodes = self.repository.search_nodes(tag_clean, limit=1)
        if nodes:
            return nodes[0]
        return None
