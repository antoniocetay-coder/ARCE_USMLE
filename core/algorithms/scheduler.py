from __future__ import annotations

import random
from typing import Any

from core.models.study_session import StudyQueueItem


def create_study_queue(mode: str, flashcards: list[dict[str, Any]], questions: list[dict[str, Any]], drills: list[dict[str, Any]] | None = None) -> list[StudyQueueItem]:
    queue: list[StudyQueueItem] = []
    if mode == "Review":
        return [StudyQueueItem("flashcard", f"flashcard:{card['id']}", "due", card) for card in flashcards]
    if mode == "QBank":
        return [StudyQueueItem("question", f"question:{question['id']}", "pending", question) for question in questions]
    if mode in ("Drills", "Discriminação", "Discriminacao"):
        drill_list = drills or []
        return [StudyQueueItem("drill", f"drill:{d.get('id', idx)}", "drill", d) for idx, d in enumerate(drill_list)]
    if mode == "Interleaved":
        drill_list = drills or []
        max_len = max(len(flashcards), len(questions), len(drill_list))
        for index in range(max_len):
            # Interleave: 2 questions, 2 flashcards, 1 discrimination drill
            queue.extend(StudyQueueItem("question", f"question:{q['id']}", "pending", q) for q in questions[index * 2:(index + 1) * 2])
            queue.extend(StudyQueueItem("flashcard", f"flashcard:{c['id']}", "due", c) for c in flashcards[index * 2:(index + 1) * 2])
            if drill_list:
                queue.extend(StudyQueueItem("drill", f"drill:{d.get('id', idx)}", "drill", d) for idx, d in enumerate(drill_list[index * 1:(index + 1) * 1]))
        return queue
    return queue


def build_study_plans(system_stats: list[dict[str, Any]], systems: list[str]) -> list[dict[str, Any]]:
    if not system_stats:
        return [{"titulo": f"Combo {index}", "sistemas": random.sample(systems, min(2, len(systems)))} for index in range(1, 4)]
    stats = {row["sistema"]: row["acertos"] / row["total"] for row in system_stats if row["total"]}
    unseen = [system for system in systems if system not in stats]
    critical = sorted((system for system, score in stats.items() if score < .5), key=stats.get)
    developing = sorted((system for system, score in stats.items() if .5 <= score < .75), key=stats.get)
    mastered = sorted((system for system, score in stats.items() if score >= .75), key=stats.get)
    return [
        {"titulo": "🚨 Foco Crítico", "sistemas": (critical + developing + systems)[:2]},
        {"titulo": "🏗️ Construção", "sistemas": (developing[-1:] + unseen + systems)[:2]},
        {"titulo": "🧭 Expansão", "sistemas": (unseen + mastered + systems)[:2]},
    ]
