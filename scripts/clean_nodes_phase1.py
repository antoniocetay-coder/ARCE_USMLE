from __future__ import annotations

import glob
import os
import re
import sqlite3
import sys

# Ensure root directory is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DB_PATH


def clean_database_nodes(db_path: str = DB_PATH) -> tuple[int, int]:
    """Executa a Fase 1: Limpa o conteúdo dos fragmentos em SQLite, mantendo os 8.046 nós intactos."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Count nodes and fragments before cleanup
    cursor.execute("SELECT COUNT(*) FROM knowledge_nodes")
    nodes_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM knowledge_fragments")
    frag_count_before = cursor.fetchone()[0]

    # Delete all text fragments and FTS contents
    cursor.execute("DELETE FROM knowledge_fragments")
    try:
        cursor.execute("DELETE FROM knowledge_fts")
    except Exception:
        pass

    conn.commit()

    # Re-insert empty placeholders for each node so schema contracts remain valid
    cursor.execute("SELECT node_id, title FROM knowledge_nodes")
    all_nodes = cursor.fetchall()

    for node_id, title in all_nodes:
        cursor.execute(
            "INSERT INTO knowledge_fragments(fragment_id, node_id, source_chunk, source_lines, sha256, content) VALUES (?, ?, ?, ?, ?, ?)",
            (f"{node_id}_meta", node_id, title, "1-1", "", f"# {title}\n*(Conteúdo limpo para novo pipeline de chunking)*"),
        )

    conn.commit()

    # Optimize disk database space
    cursor.execute("VACUUM")
    conn.close()

    return nodes_count, frag_count_before


def clean_md_files(vault_dir: str) -> int:
    """Limpa o corpo dos arquivos .md do Vault preservando apenas o frontmatter YAML."""
    if not os.path.exists(vault_dir):
        return 0

    md_files = glob.glob(os.path.join(vault_dir, "**", "*.md"), recursive=True)
    cleaned = 0

    for f in md_files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                content = file.read()

            fm_match = re.search(r"^(---\s*\n.*?\n---\s*\n)", content, re.DOTALL)
            if fm_match:
                frontmatter = fm_match.group(1)
                title_line = os.path.splitext(os.path.basename(f))[0]
                new_content = f"{frontmatter}\n# {title_line}\n"
                with open(f, "w", encoding="utf-8") as file:
                    file.write(new_content)
                cleaned += 1
        except Exception:
            pass

    return cleaned


if __name__ == "__main__":
    print("Iniciando Fase 1: Limpeza dos Nodes...")
    nodes_cnt, frags_cnt = clean_database_nodes()
    print("[OK] Banco de dados limpo com sucesso!")
    print(f"   * Nos preservados: {nodes_cnt:,}")
    print(f"   * Fragmentos de texto removidos: {frags_cnt:,}")

    vault_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "obsidian_notes"))
    cleaned_mds = clean_md_files(vault_path)
    print(f"   * Arquivos .md limpos no disco: {cleaned_mds}")
