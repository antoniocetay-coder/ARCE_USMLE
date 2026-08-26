from __future__ import annotations

from typing import Any


def get_weak_tags(stats: dict[str, dict[str, Any]], limit: int = 5, allowed_tags: set[str] | None = None) -> list[str]:
    ranked: list[tuple[str, float]] = []
    for tag, values in stats.items():
        if allowed_tags is not None and tag not in allowed_tags:
            continue
        total = int(values.get("total", 0))
        if not total:
            continue
        probability = values.get("mastery_prob")
        ranked.append((tag, float(probability) if probability is not None else int(values.get("correct", 0)) / total))
    ranked.sort(key=lambda item: item[1])
    return [tag for tag, _ in ranked[:limit]]
