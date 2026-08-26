from __future__ import annotations

import logging
from typing import List, Optional

from core.repositories.knowledge_repository import (
    KnowledgeNodeData,
    KnowledgeRepository,
)
from core.repositories.database import connection

logger = logging.getLogger(__name__)


class RAGService:

    def __init__(self, repository: KnowledgeRepository | None = None) -> None:
        self.repo = repository or KnowledgeRepository()

    def search_knowledge_context(self, query_terms: list[str], limit: int = 5) -> str:
        """Search SQLite knowledge_fts virtual table for relevant fragments matching query terms."""
        if not query_terms:
            return ""

        context_blocks = []
        with connection(self.repo.path) as conn:
            for term in query_terms:
                clean_term = term.replace('"', "").replace("'", "").strip()
                if not clean_term:
                    continue

                # Query knowledge_nodes and fragments with LIKE and FTS
                rows = conn.execute(
                    """
                    SELECT kn.title, kn.ontology_type, kf.content
                    FROM knowledge_nodes kn
                    JOIN knowledge_fragments kf ON kn.node_id = kf.node_id
                    WHERE kn.title LIKE ? OR kn.aliases LIKE ? OR kf.content LIKE ?
                    LIMIT ?
                """,
                    (f"%{clean_term}%", f"%{clean_term}%", f"%{clean_term}%", limit),
                ).fetchall()

                for r in rows:
                    block = f"--- OBSIDIAN KNOWLEDGE NODE: {r['title']} ({r['ontology_type']}) ---\n{r['content'].strip()}"
                    if block not in context_blocks:
                        context_blocks.append(block)

        if not context_blocks:
            # Fallback to direct node title or ontology lookup
            for term in query_terms:
                nodes = self.repo.list_nodes_by_ontology(term, limit=limit)
                for n in nodes:
                    full_node = self.repo.get_node_by_id(n.node_id)
                    if full_node and full_node.fragments:
                        for f in full_node.fragments[:2]:
                            block = f"--- OBSIDIAN KNOWLEDGE NODE: {full_node.title} ({full_node.ontology_type}) ---\n{f.content.strip()}"
                            if block not in context_blocks:
                                context_blocks.append(block)

        formatted_context = "\n\n".join(context_blocks[:limit])
        if formatted_context:
            logger.info("RAGService retrieved %d knowledge context blocks for terms: %s", len(context_blocks[:limit]), query_terms)
        return formatted_context

    def audit_tags(self) -> dict[str, int]:
        """Audit the knowledge graph for isolated/orphan tags that may clutter the UI. Returns dict of tag to connection count."""
        audit_report = {}
        with connection(self.repo.path) as conn:
            rows = conn.execute("""
                SELECT kn.title, (
                    SELECT COUNT(*) FROM ontology_edges WHERE source = kn.title OR target = kn.title
                ) as connection_count
                FROM knowledge_nodes kn
                WHERE connection_count < 2
                ORDER BY connection_count ASC
            """).fetchall()
            for r in rows:
                audit_report[r['title']] = r['connection_count']
        return audit_report
