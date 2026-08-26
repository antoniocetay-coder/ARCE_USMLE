from __future__ import annotations

import os
from dataclasses import dataclass

import config
from core.repositories.ai_settings_repository import AISettingsRepository

DB_PATH = config.DB_PATH


def _resolve_db_path():
    import ai.settings
    ai_mod_path = getattr(ai.settings, "DB_PATH", None)
    cfg_path = getattr(config, "DB_PATH", None)
    if ai_mod_path is not None and ai_mod_path != config.DB_PATH:
        return ai_mod_path
    return cfg_path or ai_mod_path or config.DB_PATH

GEMINI_MODELS = {
    "Gemini 3.5 Flash (Principal)": "gemini-3.5-flash",
    "Gemini 3.1 Flash Lite": "gemini-3.1-flash-lite",
    "Gemini 3.5 Flash Lite": "gemini-3.5-flash-lite",
    "Gemini 3.6 Flash": "gemini-3.6-flash",
    "Gemini 3 Flash": "gemini-3-flash-preview",
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "Gemini 2.5 Flash Lite": "gemini-2.5-flash-lite",
}
MODEL_ORDER = (
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)
MODEL_OPTIONS = {
    model_id: next(name for name, candidate in GEMINI_MODELS.items() if candidate == model_id)
    for model_id in MODEL_ORDER
}
MODEL_DESCRIPTIONS = {
    "gemini-3.5-flash": "Modelo principal selecionado. Tenta 4 chamadas com intervalo de 3s em caso de sobrecarga.",
    "gemini-3.1-flash-lite": "Modelo leve de alta disponibilidade (500 req/dia).",
    "gemini-3.5-flash-lite": "Modelo leve alternativo (500 req/dia).",
    "gemini-3.6-flash": "Modelo Gemini 3.6 Flash.",
    "gemini-3-flash-preview": "Modelo Gemini 3 Flash Preview.",
    "gemini-2.5-flash": "Modelo Gemini 2.5 Flash.",
    "gemini-2.5-flash-lite": "Modelo Gemini 2.5 Flash Lite.",
}
DEFAULT_QUESTION_MODEL = "gemini-3.5-flash"
DEFAULT_FLASHCARD_MODEL = "gemini-3.5-flash"


@dataclass(frozen=True)
class AISettings:
    api_key: str | None
    question_model: str
    flashcard_model: str
    desired_retention: float = 0.90


def load_ai_settings() -> AISettings:
    stored = AISettingsRepository(_resolve_db_path()).load_configuration()
    local_key = (stored.get("api_key") or "").strip()
    if local_key == "AIzaLocalSecret9xQ":
        local_key = ""

    environment_key = os.getenv("GEMINI_API_KEY", "").strip()
    if environment_key == "AIzaLocalSecret9xQ":
        environment_key = ""

    retention = float(stored.get("desired_retention") or 0.90)

    q_model = stored.get("question_model") or DEFAULT_QUESTION_MODEL
    if q_model not in MODEL_ORDER or q_model == "gemini-2.5-flash":
        q_model = DEFAULT_QUESTION_MODEL

    f_model = stored.get("flashcard_model") or DEFAULT_FLASHCARD_MODEL
    if f_model not in MODEL_ORDER or f_model == "gemini-2.5-flash":
        f_model = DEFAULT_FLASHCARD_MODEL

    return AISettings(
        api_key=local_key or environment_key or None,
        question_model=q_model,
        flashcard_model=f_model,
        desired_retention=retention,
    )


def save_ai_settings(api_key: str | None, question_model: str, flashcard_model: str, desired_retention: float = 0.90) -> AISettings:
    existing = AISettingsRepository(_resolve_db_path()).load_configuration()
    normalized_key = api_key.strip() if api_key and api_key.strip() else existing.get("api_key")
    AISettingsRepository(_resolve_db_path()).save_configuration(normalized_key, question_model.strip(), flashcard_model.strip(), float(desired_retention))
    from ai.client import invalidate_client
    invalidate_client()
    return load_ai_settings()


def clear_saved_api_key() -> None:
    existing = AISettingsRepository(_resolve_db_path()).load_configuration()
    AISettingsRepository(_resolve_db_path()).save_configuration(None, existing.get("question_model") or DEFAULT_QUESTION_MODEL, existing.get("flashcard_model") or DEFAULT_FLASHCARD_MODEL, float(existing.get("desired_retention") or 0.90))
    from ai.client import invalidate_client
    invalidate_client()


def restore_default_ai_settings() -> None:
    AISettingsRepository(_resolve_db_path()).save_configuration(None, DEFAULT_QUESTION_MODEL, DEFAULT_FLASHCARD_MODEL, 0.90)
    from ai.client import invalidate_client
    invalidate_client()


def mask_api_key(api_key: str | None) -> str:
    if not api_key:
        return "Nenhuma chave configurada"
    if len(api_key) <= 7:
        return "•" * len(api_key)
    return f"{api_key[:4]}...{api_key[-3:]}"
