from __future__ import annotations

import config
from core.repositories.question_repository import QuestionRepository


class HistoryService:
    def __init__(self, repository: QuestionRepository | None = None):
        self.repository = repository or QuestionRepository(config.DB_PATH)

    def answered_questions(self) -> list[dict]:
        return self.repository.get_questions()
