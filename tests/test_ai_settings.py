from __future__ import annotations

import database
from ai.settings import (
    DEFAULT_FLASHCARD_MODEL,
    DEFAULT_QUESTION_MODEL,
    GEMINI_MODELS,
    MODEL_OPTIONS,
    load_ai_settings,
    mask_api_key,
    save_ai_settings,
)


def test_local_ai_settings_override_environment_and_mask_key(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "study.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("ai.settings.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    ApplicationRepository(db_path).initialize()

    save_ai_settings("AIzaTestSecretKey123", "gemini-3.1-flash-lite", "gemini-3.5-flash-lite")
    settings = load_ai_settings()

    assert settings.api_key == "AIzaTestSecretKey123"
    assert settings.question_model == "gemini-3.1-flash-lite"
    assert settings.flashcard_model == "gemini-3.5-flash-lite"
    assert mask_api_key(settings.api_key) == "AIza...123"


def test_model_catalog_uses_api_identifiers_and_requested_defaults() -> None:
    assert GEMINI_MODELS["Gemini 3.1 Flash Lite"] == "gemini-3.1-flash-lite"
    assert list(MODEL_OPTIONS) == [
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    assert DEFAULT_QUESTION_MODEL == "gemini-3.5-flash"
    assert DEFAULT_FLASHCARD_MODEL == "gemini-3.5-flash"


def test_environment_key_is_used_when_no_local_key_exists(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "study.db"
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("ai.settings.DB_PATH", db_path)
    monkeypatch.setattr("database.DB_PATH", db_path)
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    ApplicationRepository(db_path).initialize()

    settings = load_ai_settings()

    assert settings.api_key == "env-key"
