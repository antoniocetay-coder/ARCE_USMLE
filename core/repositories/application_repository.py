from __future__ import annotations

import os
from pathlib import Path

from core.repositories.database import connection
from core.repositories.question_repository import SCHEMA

FULL_SCHEMA = SCHEMA + """
CREATE TABLE IF NOT EXISTS flashcards (id INTEGER PRIMARY KEY AUTOINCREMENT, front TEXT NOT NULL, back TEXT NOT NULL, sistema TEXT NOT NULL, tag_list TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS srs_state (object_id INTEGER NOT NULL, object_type TEXT NOT NULL, repetitions INTEGER NOT NULL DEFAULT 0, stability REAL NOT NULL DEFAULT 1.0, difficulty REAL NOT NULL DEFAULT 5.0, last_review TEXT NOT NULL, due TEXT NOT NULL, lapses INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (object_id,object_type));
CREATE TABLE IF NOT EXISTS tag_cooldown (tag TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ontology_edges (source TEXT NOT NULL, relation TEXT NOT NULL, target TEXT NOT NULL, UNIQUE(source,relation,target));
CREATE TABLE IF NOT EXISTS ai_configuration (id INTEGER PRIMARY KEY CHECK(id=1),api_key TEXT,question_model TEXT NOT NULL,flashcard_model TEXT NOT NULL, desired_retention REAL NOT NULL DEFAULT 0.90);
CREATE TABLE IF NOT EXISTS ai_response_cache (prompt_hash TEXT PRIMARY KEY, response_text TEXT NOT NULL, model_name TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS isomorphic_vignettes (id INTEGER PRIMARY KEY AUTOINCREMENT, original_question_id INTEGER NOT NULL, question_json TEXT NOT NULL, due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'scheduled', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);

-- Performance Indexes [T1]
CREATE INDEX IF NOT EXISTS idx_questions_status_system ON questions(status, sistema, answered_correctly);
CREATE INDEX IF NOT EXISTS idx_questions_answered_at ON questions(answered_at) WHERE answered_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_srs_state_due_type ON srs_state(due, object_type);
CREATE INDEX IF NOT EXISTS idx_ontology_edges_rel_target ON ontology_edges(relation, target);
CREATE INDEX IF NOT EXISTS idx_ontology_edges_rel_source ON ontology_edges(relation, source);
CREATE INDEX IF NOT EXISTS idx_confusions_pair ON confusions(tag_correct, tag_confused);
"""


class ApplicationRepository:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connection(self.path) as conn:
            conn.executescript(FULL_SCHEMA)
            try:
                conn.execute("ALTER TABLE mnemonics ADD COLUMN structured_data TEXT")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE ai_configuration ADD COLUMN desired_retention REAL NOT NULL DEFAULT 0.90")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE srs_state ADD COLUMN state INTEGER NOT NULL DEFAULT 2")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE srs_state ADD COLUMN scheduled_days REAL NOT NULL DEFAULT 1.0")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE srs_state ADD COLUMN last_review_at TEXT")
            except Exception:
                pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_type_cat ON knowledge_nodes(ontology_type, folder_category)")
            except Exception:
                pass
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (2)")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

