from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedFlashcard:
    front: str
    back: str
    system: str
    tags: list[str]
