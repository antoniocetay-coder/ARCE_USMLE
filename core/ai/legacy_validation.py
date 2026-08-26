from __future__ import annotations

import json
import re
from typing import Any


def limpar_json(texto: str) -> str:
    """Extract a JSON document from a model response, including fenced responses."""
    if not texto:
        return ""
    texto = texto.strip()
    # 1. Try regex extraction of fenced code blocks ```json ... ```
    match_fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", texto, flags=re.IGNORECASE)
    if match_fence:
        candidate = match_fence.group(1).strip()
        try:
            json.loads(candidate, strict=False)
            return candidate
        except Exception:
            pass

    # 2. Try finding outermost matching { ... }
    start_brace = texto.find("{")
    end_brace = texto.rfind("}")
    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
        candidate = texto[start_brace:end_brace + 1].strip()
        try:
            json.loads(candidate, strict=False)
            return candidate
        except Exception:
            pass

    # 3. Try finding outermost matching [ ... ]
    start_bracket = texto.find("[")
    end_bracket = texto.rfind("]")
    if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
        candidate = texto[start_bracket:end_bracket + 1].strip()
        try:
            json.loads(candidate, strict=False)
            return candidate
        except Exception:
            pass

    # 4. Fallback direct parse attempt
    try:
        json.loads(texto, strict=False)
        return texto
    except Exception:
        return ""


def validar_questao(questao: dict[str, Any], sistema: str) -> tuple[bool, str]:
    required = {"vignette", "options", "correct", "explanations", "educational_objective", "content_tags"}
    missing = required - questao.keys()
    if missing:
        return False, f"Campos ausentes: {', '.join(sorted(missing))}"
    options = questao["options"]
    if not isinstance(options, list) or len(options) < 2:
        return False, "A questão deve conter pelo menos duas alternativas."
    correct = str(questao["correct"]).strip().upper()[:1]
    labels = {str(option).strip().upper()[:1] for option in options}
    if correct not in labels:
        return False, "A alternativa correta não está presente nas opções."
    if not isinstance(questao["content_tags"], list) or not questao["content_tags"]:
        return False, "A questão deve possuir ao menos uma tag."
    return True, ""