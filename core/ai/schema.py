from __future__ import annotations

import json
import sqlite3
from typing import Dict, List

from pydantic import BaseModel, field_validator

import config
from taxonomy import TAXONOMIA_COMPLETA


def _load_all_valid_tags() -> set[str]:
    tags = {
        tag
        for sistema in TAXONOMIA_COMPLETA.values()
        for categoria in sistema.values()
        if isinstance(categoria, list)
        for tag in categoria
    }
    tags.update(TAXONOMIA_COMPLETA.keys())

    try:
        db_target = getattr(config, "DB_PATH", "app.db")
        conn = sqlite3.connect(db_target)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT node_id, title, folder_category, aliases FROM knowledge_nodes").fetchall()
        for r in rows:
            if r["title"]:
                tags.add(r["title"].strip())
                tags.add(r["title"].strip().lower())
            if r["node_id"]:
                tags.add(r["node_id"].strip())
                tags.add(r["node_id"].strip().lower())
            if r["folder_category"]:
                tags.add(r["folder_category"].strip())
                tags.add(r["folder_category"].strip().lower())
            aliases = json.loads(r["aliases"] or "[]")
            for a in aliases:
                if isinstance(a, str) and a.strip():
                    tags.add(a.strip())
                    tags.add(a.strip().lower())
        conn.close()
    except Exception:
        pass

    return tags


ALL_TAGS = _load_all_valid_tags()


class GeneratedQuestion(BaseModel):
    vignette: str
    options: list[str]
    correct: str
    explanations: dict[str, str]
    educational_objective: str
    content_tags: list[str]
    distractor_tags: dict[str, str]

    @field_validator("content_tags")
    @classmethod
    def validate_content_tags(cls, v: list[str]) -> list[str]:
        if not v:
            return ["USMLE"]
        cleaned = []
        for tag in v:
            t = str(tag).strip()
            if t:
                cleaned.append(t)
        return cleaned if cleaned else ["USMLE"]

    @field_validator("distractor_tags")
    @classmethod
    def validate_distractor_tags(cls, v: dict[str, str]) -> dict[str, str]:
        cleaned = {}
        for opt, tag in v.items():
            t = str(tag).strip()
            if t:
                cleaned[opt] = t
        return cleaned

    @field_validator("correct")
    @classmethod
    def validate_correct_option(cls, v: str) -> str:
        v = v.strip().upper()[:1]
        if v not in ["A", "B", "C", "D", "E"]:
            return "A"
        return v

    @field_validator("options")
    @classmethod
    def validate_options_length(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("A questão deve conter pelo menos duas alternativas.")
        return v


class QuestionBatch(BaseModel):
    questions: list[GeneratedQuestion]
