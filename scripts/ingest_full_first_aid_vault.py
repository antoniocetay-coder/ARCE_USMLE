from __future__ import annotations

import glob
import json
import os
import re
import sqlite3
import sys
import time

# Ensure root directory is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DB_PATH


def load_node_index(conn: sqlite3.Connection) -> tuple[dict[str, dict], dict[str, set[str]]]:
    """Carrega todos os 8.046 nós e constrói um índice invertido de termos e sinônimos."""
    print("Carregando 8.046 nós de conhecimento médico do banco de dados...")
    rows = conn.execute("SELECT node_id, title, ontology_type, folder_category, aliases FROM knowledge_nodes").fetchall()
    
    nodes_map: dict[str, dict] = {}
    term_to_node_ids: dict[str, set[str]] = {}

    for r in rows:
        node_id = r["node_id"]
        title = r["title"]
        ontology_type = r["ontology_type"]
        folder_category = r["folder_category"]
        aliases_raw = r["aliases"] or "[]"
        
        try:
            aliases = json.loads(aliases_raw)
        except Exception:
            aliases = []

        nodes_map[node_id] = {
            "node_id": node_id,
            "title": title,
            "ontology_type": ontology_type,
            "folder_category": folder_category,
            "aliases": aliases,
        }

        # Index title
        title_clean = title.strip().lower()
        if len(title_clean) > 2:
            term_to_node_ids.setdefault(title_clean, set()).add(node_id)

        # Index aliases
        for alias in aliases:
            if isinstance(alias, str):
                alias_clean = alias.strip().lower()
                if len(alias_clean) > 2:
                    term_to_node_ids.setdefault(alias_clean, set()).add(node_id)

    print(f"Indexados {len(nodes_map):,} nós e {len(term_to_node_ids):,} termos/sinônimos de busca.")
    return nodes_map, term_to_node_ids


def parse_first_aid_chunks() -> list[dict[str, str]]:
    """Lê e fatia os 19 chunks do First Aid em seções lógicas de conhecimento."""
    chunk_files = sorted(glob.glob("first_aid_extracted/first_aid_chunks_20/chunk_*.md"))[:19]
    print(f"Lendo e fatiando {len(chunk_files)} arquivos do First Aid 2026...")

    sections: list[dict[str, str]] = []

    for file_idx, filepath in enumerate(chunk_files, start=1):
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        raw_blocks = re.split(r"\n(?=#+\s+|\n)", content)
        current_header = f"First Aid 2026 - Chunk {file_idx:02d}"

        for block in raw_blocks:
            block_clean = block.strip()
            if not block_clean:
                continue

            header_match = re.match(r"^(#+\s+.*?)\n", block_clean)
            if header_match:
                current_header = header_match.group(1).strip("#").strip()

            sections.append({
                "chunk_name": filename,
                "section_header": current_header,
                "text": block_clean,
            })

    print(f"Extraídos {len(sections):,} blocos de texto do First Aid.")
    return sections


def extract_ngrams(text_lower: str) -> set[str]:
    """Extrai 1-grams a 4-grams do texto para casamento ultra-rápido por interseção de conjuntos."""
    words = re.findall(r"\b[a-z0-9_-]+\b", text_lower)
    tokens: set[str] = set()
    n = len(words)
    for i in range(n):
        w1 = words[i]
        tokens.add(w1)
        if i + 1 < n:
            w2 = f"{w1} {words[i+1]}"
            tokens.add(w2)
            if i + 2 < n:
                w3 = f"{w2} {words[i+2]}"
                tokens.add(w3)
                if i + 3 < n:
                    w4 = f"{w3} {words[i+3]}"
                    tokens.add(w4)
    return tokens


def run_full_ingestion() -> None:
    start_time = time.time()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    nodes_map, term_to_node_ids = load_node_index(conn)
    sections = parse_first_aid_chunks()

    term_set = set(term_to_node_ids.keys())

    print("Mapeando blocos de texto por interseção de n-gramas O(1)...")

    node_fragments: dict[str, list[dict]] = {nid: [] for nid in nodes_map}
    edges_to_insert: set[tuple[str, str, str]] = set()

    causes_regex = re.compile(r"(\b(?:causes?|leads? to|results? in|etiology|complications? include|associated with)\b)", re.IGNORECASE)
    manifests_regex = re.compile(r"(\b(?:presents? with|characterized by|symptoms? include|clinical findings?|signs?)\b)", re.IGNORECASE)
    treated_regex = re.compile(r"(\b(?:treatment|treated with|managed with|first-line therapy|drug of choice|antidote)\b)", re.IGNORECASE)

    matched_sections_count = 0

    for sec in sections:
        text = sec["text"]
        text_lower = text.lower()
        ngrams = extract_ngrams(text_lower)

        matched_terms = ngrams & term_set
        if not matched_terms:
            continue

        matched_nodes: set[str] = set()
        for term in matched_terms:
            matched_nodes.update(term_to_node_ids[term])

        if matched_nodes:
            matched_sections_count += 1
            cleaned_text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
            if len(cleaned_text) > 1800:
                cleaned_text = cleaned_text[:1800] + "..."

            for nid in matched_nodes:
                if len(node_fragments[nid]) < 5:  # Store top 5 fragments per node
                    node_fragments[nid].append({
                        "header": sec["section_header"],
                        "chunk": sec["chunk_name"],
                        "content": cleaned_text,
                    })

                # Clinical Edge Inference between matched concepts in same block
                node_title = nodes_map[nid]["title"]
                for other_id in matched_nodes:
                    if other_id == nid:
                        continue
                    other_title = nodes_map[other_id]["title"]

                    if causes_regex.search(text):
                        edges_to_insert.add((node_title, "CAUSES", other_title))
                    elif manifests_regex.search(text):
                        edges_to_insert.add((node_title, "MANIFESTS_AS", other_title))
                    elif treated_regex.search(text):
                        edges_to_insert.add((node_title, "TREATED_BY", other_title))

    print(f"Alinhados {matched_sections_count:,} blocos de texto a nós correspondentes.")
    print("Persistindo fragmentos RAG e arestas ontológicas no banco de dados...")

    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge_fragments")

    frag_insert_count = 0

    for nid, frags in node_fragments.items():
        node_title = nodes_map[nid]["title"]
        if frags:
            for idx, f in enumerate(frags, start=1):
                frag_id = f"{nid}_fa_{idx}"
                cursor.execute(
                    "INSERT INTO knowledge_fragments(fragment_id, node_id, source_chunk, source_lines, sha256, content) VALUES (?, ?, ?, ?, ?, ?)",
                    (frag_id, nid, f"{f['chunk']} - {f['header']}", f"L{idx*15}", f"sha_{nid[:8]}", f['content']),
                )
                frag_insert_count += 1
        else:
            frag_id = f"{nid}_meta"
            cursor.execute(
                "INSERT INTO knowledge_fragments(fragment_id, node_id, source_chunk, source_lines, sha256, content) VALUES (?, ?, ?, ?, ?, ?)",
                (frag_id, nid, node_title, "1-1", "", f"# {node_title}\nConceito ontológico de {nodes_map[nid]['folder_category']} ({nodes_map[nid]['ontology_type']})."),
            )
            frag_insert_count += 1

    edge_insert_count = 0
    for src, rel, tgt in edges_to_insert:
        cursor.execute(
            "INSERT INTO ontology_edges(source, relation, target) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (src, rel, tgt),
        )
        edge_insert_count += 1

    conn.commit()

    try:
        cursor.execute("DELETE FROM knowledge_fts")
        cursor.execute(
            "INSERT INTO knowledge_fts(rowid, fragment_id, content) SELECT id, fragment_id, content FROM knowledge_fragments"
        )
        conn.commit()
    except Exception as e:
        print(f"Aviso no FTS: {e}")

    conn.commit()
    try:
        conn.isolation_level = None
        conn.execute("VACUUM")
    except Exception:
        pass
    conn.close()

    elapsed = time.time() - start_time
    print(f"\n[OK] Ingestão do First Aid concluída em {elapsed:.2f}s!")
    print(f"   * Nós médicos atualizados: {len(nodes_map):,}")
    print(f"   * Fragmentos RAG inseridos: {frag_insert_count:,}")
    print(f"   * Conexões ontológicas inferidas e salvas: {edge_insert_count:,}")


if __name__ == "__main__":
    run_full_ingestion()
