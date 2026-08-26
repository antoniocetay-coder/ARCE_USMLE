from __future__ import annotations

from typing import Protocol

from core.repositories.ai_settings_repository import AISettingsRepository


class AISettingsConfigurationRepository(Protocol):
    def load_configuration(self) -> dict[str, str | None]: ...


class AISettingsService:
    """Application boundary consumed by NiceGUI settings callbacks."""

    def __init__(self, repository: AISettingsConfigurationRepository | None = None) -> None:
        self.repository = repository or AISettingsRepository()

    def has_saved_api_key(self) -> bool:
        return bool(self.repository.load_configuration().get("api_key"))
