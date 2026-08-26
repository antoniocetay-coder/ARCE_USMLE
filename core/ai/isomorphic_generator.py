from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ai.client import generate_text
from ai.settings import load_ai_settings
from core.ai.legacy_validation import limpar_json
from core.exceptions import QuestionGenerationError
from core.repositories.database import connection

logger = logging.getLogger(__name__)


def construir_prompt_isomorfico(original_vignette: str, objective: str, correct_opt: str, correct_exp: str, options: list[str]) -> str:
    return f"""You are an elite NBME-style USMLE question writer and cognitive psychologist.
The student recently solved (or struggled with) this USMLE question:

ORIGINAL VIGNETTE:
{original_vignette}

EDUCATIONAL OBJECTIVE (INVARIANT CLINICAL RULE):
{objective}

CORRECT ANSWER ({correct_opt}):
{correct_exp}

ORIGINAL OPTIONS:
{json.dumps(options)}

TASK: ISOMORPHIC TRANSFER VIGNETTE GENERATION
Generate a NEW, ISOMORPHIC USMLE clinical vignette that tests the EXACT SAME underlying invariant pathophysiology, mechanism, or clinical rule, but with:
1. DIFFERENT SUPERFICIAL SURFACE FEATURES:
   - Alter the patient age, sex, profession, or clinical setting (e.g., if the original was an elderly male in the ICU, make this a young female athlete in the outpatient clinic).
   - Change the initial presenting chief complaint, but keep the exact same underlying biochemical/histopathological disease state.
2. SAME COGNITIVE DEPTH: Require the student to recognize the invariant pattern, eliminating superficial memorization.
3. 5 HIGH-QUALITY OPTIONS (A, B, C, D, E) with plausible distractors.
4. STRICT LANGUAGE RULE: All text, options, and explanations MUST be strictly in English.

RETURN FORMAT:
Return ONLY valid JSON in this exact structure:
{{
    "vignette": "A 28-year-old female presents with...",
    "options": [
        "A) Option 1",
        "B) Option 2",
        "C) Option 3",
        "D) Option 4",
        "E) Option 5"
    ],
    "correct": "B",
    "explanations": {{
        "A": "Why A is incorrect.",
        "B": "Why B is correct (explaining the invariant mechanism).",
        "C": "Why C is incorrect.",
        "D": "Why D is incorrect.",
        "E": "Why E is incorrect."
    }},
    "educational_objective": "{objective}",
    "content_tags": ["Isomorphic_Transfer"]
}}
"""


def gerar_vinheta_isomorfica(questao_original: dict[str, Any]) -> dict[str, Any]:
    vignette = questao_original.get("vignette", "")
    objective = questao_original.get("educational_objective", "Core USMLE Mechanism")
    correct_opt = questao_original.get("correct", "A")
    explanations = questao_original.get("explanations", {})
    correct_exp = explanations.get(correct_opt, "Correct mechanism.")
    options = questao_original.get("options", [])

    prompt = construir_prompt_isomorfico(vignette, objective, correct_opt, correct_exp, options)

    try:
        raw_text = generate_text(prompt, load_ai_settings().question_model, response_json=True, use_cache=True)
        cleaned = limpar_json(raw_text)
        data = json.loads(cleaned if cleaned else raw_text)
        if isinstance(data, dict) and "vignette" in data and "options" in data:
            return data
        raise QuestionGenerationError("Estrutura JSON inválida retornada para a vinheta isomórfica.")
    except Exception as error:
        logger.warning("Falha ao gerar vinheta isomórfica: %s", error)
        raise QuestionGenerationError(f"Não foi possível gerar a vinheta isomórfica: {error}") from error


def agendar_vinheta_isomorfica(original_id: int, questao_original: dict[str, Any], sistema: str = "General_Principles", db_path=None) -> int | None:
    import config
    try:
        isomorphic_q = gerar_vinheta_isomorfica(questao_original)
        target_db = db_path or config.DB_PATH
        
        # Calculate dynamic FSRS-based interval
        interval_days = 2
        try:
            with connection(target_db) as conn:
                tag_list = questao_original.get("content_tags", [])
                if tag_list:
                    primary_tag = tag_list[0]
                    row = conn.execute(
                        "SELECT stability FROM srs_state WHERE object_id = ? AND object_type = 'tag'",
                        (primary_tag,)
                    ).fetchone()
                    if row and row["stability"]:
                        s = float(row["stability"])
                        # FSRS optimal interval for transfer rehearsal (target retention 90%)
                        calculated = round(s * (1.0 / 0.90 - 1.0) / (1.0 / 0.90 - 1.0))
                        interval_days = min(max(calculated, 1), 7)
        except Exception as e:
            logger.debug("Could not determine dynamic FSRS stability: %s", e)

        due_date = (datetime.now(timezone.utc) + timedelta(days=interval_days)).date().isoformat()
        q_json = json.dumps(isomorphic_q, ensure_ascii=False)

        with connection(target_db) as conn:
            cur = conn.execute(
                "INSERT INTO isomorphic_vignettes (original_question_id, question_json, due_date, status) VALUES (?, ?, ?, 'scheduled')",
                (original_id, q_json, due_date),
            )
            # Also insert into questions so it appears in due questions for restudy
            conn.execute(
                "INSERT INTO questions (sistema, dificuldade, question_json, status, tag_list) VALUES (?, 'Medium', ?, 'pending', ?)",
                (sistema, q_json, "Isomorphic_Transfer|" + "|".join(questao_original.get("content_tags", []))),
            )
            return cur.lastrowid
    except Exception as error:
        logger.warning("Erro ao agendar vinheta isomórfica: %s", error)
        return None
