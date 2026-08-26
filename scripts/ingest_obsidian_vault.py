from __future__ import annotations

import glob
import json
import logging
import os
import re
import sys

# Ensure current directory is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.repositories.knowledge_repository import KnowledgeRepository
from database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("ingest_obsidian")


def ingest_vault(vault_path: str) -> None:
    init_db()
    repo = KnowledgeRepository()
    md_files = glob.glob(os.path.join(vault_path, "**", "*.md"), recursive=True)
    logger.info("Found %d markdown files in vault at %s", len(md_files), vault_path)

    success_count = 0
    for f in md_files:
        rel_path = os.path.relpath(f, vault_path)
        parts = rel_path.split(os.sep)
        folder_category = parts[1] if len(parts) > 1 else parts[0]
        filename = os.path.basename(f)
        title = os.path.splitext(filename)[0]

        try:
            with open(f, "r", encoding="utf-8") as file:
                content = file.read()
        except Exception as e:
            logger.warning("Could not read file %s: %s", f, e)
            continue

        fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        node_id = f"node_{title.lower().replace(' ', '_')}"
        ontology_type = "other_medical_concept"
        aliases = []

        if fm_match:
            fm_text = fm_match.group(1)
            nid_m = re.search(r'node_id:\s*"([^"]+)"', fm_text)
            if nid_m:
                node_id = nid_m.group(1)

            type_m = re.search(r'type:\s*"([^"]+)"', fm_text)
            if type_m:
                ontology_type = type_m.group(1)

            aliases_m = re.search(r"aliases:\s*\[(.*?)\]", fm_text)
            if aliases_m and aliases_m.group(1).strip():
                try:
                    aliases = json.loads(f"[{aliases_m.group(1)}]")
                except Exception:
                    aliases = [a.strip().strip('"').strip("'") for a in aliases_m.group(1).split(",") if a.strip()]

        # Parse NODE-SEMANTIC fragments
        fragments = []
        frag_matches = re.finditer(r"<!-- NODE-SEMANTIC:\s*(\S+)\s+TARGET\s+\S+\s+START -->(.*?)<!-- NODE-SEMANTIC:\s*\1\s+TARGET\s+\S+\s+END -->", content, re.DOTALL)
        for match in frag_matches:
            frag_id = match.group(1)
            frag_body = match.group(2).strip()

            chunk_m = re.search(r"_Source:\s*`([^`]+)`,?\s*lines\s*([\d–-]+);?\s*(?:SHA-256:\s*`([^`]+)`)?", frag_body)
            source_chunk = chunk_m.group(1) if chunk_m else None
            source_lines = chunk_m.group(2) if chunk_m else None
            sha256 = chunk_m.group(3) if chunk_m else None

            fragments.append(
                {
                    "fragment_id": frag_id,
                    "source_chunk": source_chunk,
                    "source_lines": source_lines,
                    "sha256": sha256,
                    "content": frag_body,
                }
            )

        # If no semantic tags, treat full body as 1 fragment
        if not fragments:
            body_text = content[fm_match.end() :] if fm_match else content
            if body_text.strip():
                fragments.append({"fragment_id": f"{node_id}_full", "content": body_text.strip()})

        repo.save_node(node_id, title, ontology_type, aliases, folder_category, fragments)
        success_count += 1

    logger.info("Successfully ingested %d / %d knowledge nodes into SQLite database.", success_count, len(md_files))


if __name__ == "__main__":
    vault_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "obsidian_notes"))
    ingest_vault(vault_dir)
