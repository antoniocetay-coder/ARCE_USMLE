from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, List, Optional

from core.repositories.database import connection

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeFragmentData:
    id: int
    node_id: str
    fragment_id: str
    source_chunk: str | None
    source_lines: str | None
    sha256: str | None
    content: str


@dataclass
class KnowledgeNodeData:
    node_id: str
    title: str
    ontology_type: str
    aliases: list[str]
    folder_category: str
    fragments: list[KnowledgeFragmentData]


import config


class KnowledgeRepository:

    def __init__(self, path: Path | str | None = None):
        self.path = path if path is not None else config.DB_PATH

    def save_node(self, node_id: str, title: str, ontology_type: str, aliases: list[str], folder_category: str, fragments: list[dict]) -> None:
        aliases_json = json.dumps(aliases, ensure_ascii=False)
        with connection(self.path) as conn:
            conn.execute(
                """
                INSERT INTO knowledge_nodes (node_id, title, ontology_type, aliases, folder_category, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(node_id) DO UPDATE SET
                    title=excluded.title,
                    ontology_type=excluded.ontology_type,
                    aliases=excluded.aliases,
                    folder_category=excluded.folder_category,
                    updated_at=CURRENT_TIMESTAMP
            """,
                (node_id, title, ontology_type, aliases_json, folder_category),
            )

            # Clear existing fragments for update
            conn.execute("DELETE FROM knowledge_fragments WHERE node_id = ?", (node_id,))

            for frag in fragments:
                cursor = conn.execute(
                    """
                    INSERT INTO knowledge_fragments (node_id, fragment_id, source_chunk, source_lines, sha256, content)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        node_id,
                        frag.get("fragment_id", ""),
                        frag.get("source_chunk"),
                        frag.get("source_lines"),
                        frag.get("sha256"),
                        frag.get("content", ""),
                    ),
                )
                frag_rowid = cursor.lastrowid
                conn.execute(
                    """
                    INSERT INTO knowledge_fts(rowid, title, ontology_type, aliases, content)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (frag_rowid, title, ontology_type, aliases_json, frag.get("content", "")),
                )
            conn.commit()

    def get_node_by_id(self, node_id: str) -> KnowledgeNodeData | None:
        with connection(self.path) as conn:
            row = conn.execute("SELECT * FROM knowledge_nodes WHERE node_id = ?", (node_id,)).fetchone()
            if not row:
                return None
            aliases = json.loads(row["aliases"] or "[]")
            frag_rows = conn.execute("SELECT * FROM knowledge_fragments WHERE node_id = ?", (node_id,)).fetchall()
            fragments = [
                KnowledgeFragmentData(
                    id=f["id"],
                    node_id=f["node_id"],
                    fragment_id=f["fragment_id"],
                    source_chunk=f["source_chunk"],
                    source_lines=f["source_lines"],
                    sha256=f["sha256"],
                    content=f["content"],
                )
                for f in frag_rows
            ]
            return KnowledgeNodeData(
                node_id=row["node_id"],
                title=row["title"],
                ontology_type=row["ontology_type"],
                aliases=aliases,
                folder_category=row["folder_category"],
                fragments=fragments,
            )

    def list_nodes_by_ontology(self, ontology_type: str, limit: int = 100, exclude_orphans: bool = False) -> list[KnowledgeNodeData]:
        with connection(self.path) as conn:
            if exclude_orphans:
                query = """
                    SELECT kn.* FROM knowledge_nodes kn
                    WHERE kn.ontology_type = ? AND (
                        SELECT COUNT(*) FROM ontology_edges WHERE source = kn.title OR target = kn.title
                    ) >= 2
                    LIMIT ?
                """
            else:
                query = "SELECT * FROM knowledge_nodes WHERE ontology_type = ? LIMIT ?"
                
            rows = conn.execute(query, (ontology_type, limit)).fetchall()
            nodes = []
            for r in rows:
                aliases = json.loads(r["aliases"] or "[]")
                nodes.append(
                    KnowledgeNodeData(
                        node_id=r["node_id"],
                        title=r["title"],
                        ontology_type=r["ontology_type"],
                        aliases=aliases,
                        folder_category=r["folder_category"],
                        fragments=[],
                    )
                )
            return nodes

    def search_nodes(self, query: str, limit: int = 12) -> list[KnowledgeNodeData]:
        with connection(self.path) as conn:
            rows = conn.execute(
                "SELECT * FROM knowledge_nodes WHERE title LIKE ? OR aliases LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            nodes = []
            for r in rows:
                aliases = json.loads(r["aliases"] or "[]")
                nodes.append(
                    KnowledgeNodeData(
                        node_id=r["node_id"],
                        title=r["title"],
                        ontology_type=r["ontology_type"],
                        aliases=aliases,
                        folder_category=r["folder_category"],
                        fragments=[],
                    )
                )
            return nodes

    def get_ontology_counts(self) -> dict:
        with connection(self.path) as conn:
            rows = conn.execute("SELECT ontology_type, COUNT(*) as count FROM knowledge_nodes GROUP BY ontology_type").fetchall()
            return {r["ontology_type"]: r["count"] for r in rows}

    def filter_nodes_paginated(
        self,
        query: str = "",
        category: str = "",
        ontology_type: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[KnowledgeNodeData]]:
        with connection(self.path) as conn:
            where_clauses = ["1=1"]
            params: list[Any] = []

            if query.strip():
                q_clean = f"%{query.strip()}%"
                where_clauses.append("(title LIKE ? OR aliases LIKE ? OR node_id LIKE ?)")
                params.extend([q_clean, q_clean, q_clean])

            if category.strip() and category != "Todas as Categorias":
                where_clauses.append("folder_category = ?")
                params.append(category.strip())

            if ontology_type.strip() and ontology_type != "Todos os Tipos":
                where_clauses.append("ontology_type = ?")
                params.append(ontology_type.strip())

            where_str = " AND ".join(where_clauses)

            count_row = conn.execute(f"SELECT COUNT(*) as total FROM knowledge_nodes WHERE {where_str}", params).fetchone()
            total_count = count_row["total"] if count_row else 0

            data_query = f"SELECT * FROM knowledge_nodes WHERE {where_str} ORDER BY title ASC LIMIT ? OFFSET ?"
            data_params = params + [limit, offset]
            rows = conn.execute(data_query, data_params).fetchall()

            nodes = []
            for r in rows:
                aliases = json.loads(r["aliases"] or "[]")
                nodes.append(
                    KnowledgeNodeData(
                        node_id=r["node_id"],
                        title=r["title"],
                        ontology_type=r["ontology_type"],
                        aliases=aliases,
                        folder_category=r["folder_category"],
                        fragments=[],
                    )
                )
            return total_count, nodes

    def get_prerequisite_sources(self, target_tag: str) -> list[str]:
        try:
            with connection(self.path) as conn:
                rows = conn.execute(
                    "SELECT source FROM ontology_edges WHERE LOWER(target) = LOWER(?) AND relation = 'PREREQUISITE_FOR'",
                    (target_tag.strip(),),
                ).fetchall()
                return [r["source"] for r in rows]
        except sqlite3.OperationalError:
            return []

    def get_dependent_targets(self, source_tag: str) -> list[str]:
        try:
            with connection(self.path) as conn:
                rows = conn.execute(
                    "SELECT target FROM ontology_edges WHERE LOWER(source) = LOWER(?) AND relation = 'PREREQUISITE_FOR'",
                    (source_tag.strip(),),
                ).fetchall()
                return [r["target"] for r in rows]
        except sqlite3.OperationalError:
            return []

    def get_ontology_relations(self, tag: str) -> list[dict[str, str]]:
        try:
            with connection(self.path) as conn:
                tag_clean = tag.strip().lower()
                node_row = conn.execute(
                    "SELECT title, aliases FROM knowledge_nodes WHERE LOWER(title) = ? OR LOWER(node_id) = ? LIMIT 1",
                    (tag_clean, tag_clean),
                ).fetchone()

                search_terms = {tag_clean}
                if node_row:
                    search_terms.add(node_row["title"].strip().lower())
                    aliases = json.loads(node_row["aliases"] or "[]")
                    for a in aliases:
                        if isinstance(a, str) and a.strip():
                            search_terms.add(a.strip().lower())

                placeholders = ", ".join(["?"] * len(search_terms))
                terms_list = list(search_terms)
                query = f"SELECT relation, source, target FROM ontology_edges WHERE LOWER(source) IN ({placeholders}) OR LOWER(target) IN ({placeholders})"
                rows = conn.execute(query, terms_list + terms_list).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def get_all_nodes_summary(self) -> list[str]:
        try:
            with connection(self.path) as conn:
                rows = conn.execute("SELECT title FROM knowledge_nodes").fetchall()
                return [r["title"] for r in rows]
        except sqlite3.OperationalError:
            return []

    def get_all_edges_summary(self) -> list[dict[str, str]]:
        try:
            with connection(self.path) as conn:
                rows = conn.execute("SELECT source, relation, target FROM ontology_edges").fetchall()
                return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

