from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import config
from core.repositories.database import connection

logger = logging.getLogger(__name__)


def compute_prompt_hash(prompt: str, model: str) -> str:
    key = f"{model.strip()}:{prompt.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def get_cached_response(prompt: str, model: str, db_path: Path | str | None = None) -> str | None:
    h = compute_prompt_hash(prompt, model)
    try:
        with connection(db_path or config.DB_PATH) as conn:
            row = conn.execute("SELECT response_text FROM ai_response_cache WHERE prompt_hash = ?", (h,)).fetchone()
            if row:
                return row["response_text"]
    except Exception as error:
        logger.warning("Erro ao consultar ai_response_cache: %s", error)
    return None


def store_cached_response(prompt: str, model: str, response_text: str, db_path: Path | str | None = None) -> None:
    if not response_text or not response_text.strip():
        return
    h = compute_prompt_hash(prompt, model)
    try:
        with connection(db_path or config.DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ai_response_cache (prompt_hash, response_text, model_name) VALUES (?, ?, ?)",
                (h, response_text.strip(), model),
            )
    except Exception as error:
        logger.warning("Erro ao salvar em ai_response_cache: %s", error)
