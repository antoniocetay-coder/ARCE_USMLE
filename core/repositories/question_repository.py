from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from core.algorithms.mastery import update_bkt
from core.exceptions import DatabaseError
from core.repositories.database import connection

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, sistema TEXT NOT NULL, dificuldade TEXT NOT NULL, question_json TEXT NOT NULL, answered_correctly INTEGER, response_time INTEGER, confidence_level TEXT, status TEXT NOT NULL DEFAULT 'pending', tag_list TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, answered_at TEXT);
CREATE TABLE IF NOT EXISTS generated_batches (request_id TEXT PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS tag_stats (tag TEXT PRIMARY KEY, correct INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0, mastery_prob REAL);
CREATE TABLE IF NOT EXISTS erros_por_sistema (sistema TEXT PRIMARY KEY, total INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS confusions (tag_correct TEXT NOT NULL, tag_confused TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (tag_correct, tag_confused));
"""
@dataclass(frozen=True)
class BatchSaveResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    duplicate: bool = False
class QuestionRepository:
    def __init__(self, path: Path | str | None = None):
        self.path = path if path is not None else config.DB_PATH
    def initialize_schema(self) -> None:
        with connection(self.path) as conn: conn.executescript(SCHEMA)
    def save_pending_questions_batch(self, entries: list[dict[str, Any]], *, request_id: str) -> BatchSaveResult:
        if not entries: return BatchSaveResult()
        try:
            with connection(self.path) as conn:
                try: conn.execute("INSERT INTO generated_batches(request_id) VALUES (?)", (request_id,))
                except sqlite3.IntegrityError: return BatchSaveResult(duplicate=True)
                rows=[]
                for entry in entries:
                    question=entry['question']; tags=question['content_tags']
                    cursor=conn.execute("INSERT INTO questions (sistema,dificuldade,question_json,status,tag_list) VALUES (?,?,?,'pending',?)", (entry['sistema'],entry['dificuldade'],json.dumps(question,ensure_ascii=False), '|'.join(tags)))
                    rows.append({'id':int(cursor.lastrowid),'sistema':entry['sistema'],'dificuldade':entry['dificuldade'],'question_json':json.dumps(question,ensure_ascii=False),'status':'pending'})
                return BatchSaveResult(rows)
        except sqlite3.Error as error: raise DatabaseError('Could not save question batch.') from error
    def get_pending_questions(self) -> list[dict[str,Any]]:
        with connection(self.path) as conn: return [dict(row) for row in conn.execute("SELECT * FROM questions WHERE status='pending' ORDER BY id")]
    def get_all_question_ids(self) -> set[int]:
        with connection(self.path) as conn: return {row['id'] for row in conn.execute('SELECT id FROM questions').fetchall()}
    def get_questions(self) -> list[dict[str,Any]]:
        with connection(self.path) as conn: return [dict(row) for row in conn.execute("SELECT * FROM questions WHERE status='answered' ORDER BY answered_at DESC,id DESC")]
    def get_incorrect_questions(self, sistema: str = "Todos os Sistemas", limit: int = 50) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            sql = "SELECT id, sistema, dificuldade, question_json, answered_correctly, created_at FROM questions WHERE answered_correctly = 0 OR confidence_level = 'Chute Cego'"
            params: list[Any] = []
            if sistema and sistema != "Todos os Sistemas":
                sql += " AND sistema = ?"
                params.append(sistema)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()

            result = []
            for r in rows:
                try:
                    q_dict = json.loads(r["question_json"])
                    q_dict["id"] = r["id"]
                    q_dict["sistema"] = r["sistema"]
                    q_dict["dificuldade"] = r["dificuldade"]
                    result.append(q_dict)
                except Exception as error:
                    import logging
                    logging.getLogger(__name__).warning("Falha ao carregar questão legada do banco: %s", error)
            return result
    def prepare_incorrect_for_restudy(self, limit: int = 10) -> list[dict[str,Any]]:
        incorrect = self.get_incorrect_questions()[:limit]
        if not incorrect: return []
        ids = [row["id"] for row in incorrect]
        with connection(self.path) as conn:
            conn.execute(f"UPDATE questions SET status='pending' WHERE id IN ({','.join('?' * len(ids))})", ids)
        for row in incorrect:
            row["status"] = "pending"
            if "question_json" not in row:
                row["question_json"] = json.dumps(row, ensure_ascii=False)
        return incorrect

    def record_question_result(self, question_id:int, system:str,is_correct:bool,tags:Iterable[str],time_taken:int,confidence:str)->bool:
        try:
            with connection(self.path) as conn:
                updated=conn.execute("UPDATE questions SET status='answered',answered_correctly=?,response_time=?,confidence_level=?,answered_at=? WHERE id=? AND status='pending'",(int(is_correct),time_taken,confidence,datetime.now(timezone.utc).isoformat(),question_id))
                if updated.rowcount != 1: return False
                for tag in tags:
                    row=conn.execute('SELECT correct,total,mastery_prob FROM tag_stats WHERE tag=?',(tag,)).fetchone(); current=float(row['mastery_prob']) if row and row['mastery_prob'] is not None else .15
                    correct=(int(row['correct']) if row else 0)+int(is_correct); total=(int(row['total']) if row else 0)+1
                    conn.execute("INSERT INTO tag_stats(tag,correct,total,mastery_prob) VALUES (?,?,?,?) ON CONFLICT(tag) DO UPDATE SET correct=excluded.correct,total=excluded.total,mastery_prob=excluded.mastery_prob",(tag,correct,total,update_bkt(current,is_correct,confidence)))
                if not is_correct: conn.execute("INSERT INTO erros_por_sistema(sistema,total) VALUES (?,1) ON CONFLICT(sistema) DO UPDATE SET total=total+1",(system,))
                return True
        except sqlite3.Error as error: raise DatabaseError('Could not record answer.') from error
    def register_confusion(self, correct_tag:str, confused_tag:str)->None:
        with connection(self.path) as conn: conn.execute("INSERT INTO confusions(tag_correct,tag_confused,count) VALUES (?,?,1) ON CONFLICT(tag_correct,tag_confused) DO UPDATE SET count=count+1",(correct_tag,confused_tag))
