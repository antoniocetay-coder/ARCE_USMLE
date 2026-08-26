from __future__ import annotations

from enum import Enum


class MasteryLevel(str, Enum):
    NEW = "new"
    LEARNING = "learning"
    CONSOLIDATED = "consolidated"
    MASTERED = "mastered"


def update_bkt(probability: float, is_correct: bool, confidence: str, difficulty: str = "Médio", force_mastery: float | None = None) -> float:
    if force_mastery is not None:
        return force_mastery
        
    slip = .1 if confidence == "Certeza Absoluta" else .15
    guess = .2 if confidence == "Chute Cego" else .1
    learning = .1
    probability = (probability * (1 - slip)) / (probability * (1 - slip) + (1 - probability) * guess) if is_correct else (probability * slip) / (probability * slip + (1 - probability) * (1 - guess))
    new_prob = probability + (1 - probability) * learning
    
    # Difficulty Cap
    if difficulty == "Fácil":
        return min(new_prob, 0.64)
    elif difficulty == "Médio":
        return min(new_prob, 0.89)
    else:
        # Difícil: sem cap estrito, permite chegar a 0.99
        return min(new_prob, 0.99)


def classify_mastery(probability: float | None) -> MasteryLevel:
    if probability is None or probability < .30:
        return MasteryLevel.NEW
    if probability < .65:
        return MasteryLevel.LEARNING
    if probability < .90:
        return MasteryLevel.CONSOLIDATED
    return MasteryLevel.MASTERED
