from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)

def extract_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not starts:
        return ""
    candidate = text[min(starts):]
    try:
        json.loads(candidate)
    except json.JSONDecodeError:
        return ""
    return candidate

def validate_question(question: Any, system: str, *, valid_tags: Iterable[str] | None = None) -> ValidationResult:
    errors: list[str] = []
    if not isinstance(question, dict): return ValidationResult(False, ["Question must be an object."])
    required = ("vignette", "options", "correct", "explanations", "educational_objective", "content_tags", "difficulty", "cognitive_order")
    errors += [f"Missing required field: {field}" for field in required if not question.get(field)]
    options = question.get("options")
    if not isinstance(options, list) or not 2 <= len(options) <= 5: errors.append("Question must have 2 to 5 options.")
    else:
        labels = [str(option).strip().upper()[:1] for option in options]
        if len(set(labels)) != len(labels) or any(not label.isalpha() for label in labels): errors.append("Option identifiers are incoherent.")
        if str(question.get("correct", "")).strip().upper()[:1] not in labels: errors.append("Correct answer is not among options.")
        explanations = question.get("explanations")
        if not isinstance(explanations, dict) or any(not str(explanations.get(label, "")).strip() for label in labels): errors.append("Every option needs an explanation.")
    tags = question.get("content_tags")
    if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags): errors.append("Tags are invalid.")
    elif valid_tags is not None and not set(tags).issubset(set(valid_tags)): errors.append("Question contains tag outside taxonomy.")
    if not isinstance(system, str) or not system.strip(): errors.append("System is invalid.")
    return ValidationResult(not errors, errors)
