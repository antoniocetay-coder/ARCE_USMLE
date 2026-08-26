from __future__ import annotations

import ast
from pathlib import Path

from core.services.ai_settings_service import AISettingsService


class InMemoryAISettingsRepository:
    def __init__(self, configuration: dict[str, str | None]) -> None:
        self.configuration = configuration

    def load_configuration(self) -> dict[str, str | None]:
        return self.configuration


def test_ai_settings_service_reports_local_key_presence() -> None:
    with_local_key = AISettingsService(InMemoryAISettingsRepository({"api_key": "AIzaLocal"}))
    with_whitespace_key = AISettingsService(InMemoryAISettingsRepository({"api_key": "  "}))
    without_local_key = AISettingsService(InMemoryAISettingsRepository({"api_key": None}))

    assert with_local_key.has_saved_api_key()
    assert with_whitespace_key.has_saved_api_key()
    assert not without_local_key.has_saved_api_key()


def test_ai_settings_repository_reads_saved_configuration(tmp_path) -> None:
    db_path = tmp_path / "study.db"
    import database
    database.DB_PATH = db_path
    from core.repositories.ai_settings_repository import AISettingsRepository

    database.init_db()
    from core.repositories.application_repository import ApplicationRepository
    try:
        ApplicationRepository(db_path).initialize()
    except NameError:
        pass
    repo = AISettingsRepository(db_path)
    repo.save_configuration("AIzaLocal", "question-model", "flashcard-model")

    assert repo.load_configuration() == {
        "api_key": "AIzaLocal",
        "question_model": "question-model",
        "flashcard_model": "flashcard-model",
        "desired_retention": 0.90,
    }


def test_settings_page_does_not_import_database_directly() -> None:
    page = Path(__file__).parents[1] / "pages" / "settings.py"
    tree = ast.parse(page.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "database" not in imported_modules
