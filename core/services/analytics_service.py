from __future__ import annotations

from typing import Any

import config
from core.repositories.analytics_repository import AnalyticsRepository


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository | None = None):
        self.repository = repository or AnalyticsRepository(config.DB_PATH)

    def dashboard(self) -> dict[str, Any]:
        return {
            "systems": self.repository.get_system_stats(),
            "metacognition": self.repository.get_metacognition_stats(),
            "time": self.repository.get_time_stats(),
            "forecast": self.repository.get_fsrs_forecast(),
            "confusions": self.repository.get_global_confusions(),
            "calibration": self.repository.get_metacognitive_calibration(),
            "prediction": self.repository.get_usmle_pass_prediction(),
        }

    def get_metacognitive_calibration(self) -> dict[str, Any]:
        return self.repository.get_metacognitive_calibration()

    def get_usmle_pass_prediction(self) -> dict[str, Any]:
        return self.repository.get_usmle_pass_prediction()

    def get_user_streak_data(self) -> dict[str, Any]:
        return self.repository.get_user_streak_data()

    def get_top_confounders(self, tag: str, limit: int = 3) -> list[str]:
        return self.repository.get_top_confounders(tag, limit)

    def get_consolidated_tags(self) -> list[dict]:
        return self.repository.get_consolidated_tags()
