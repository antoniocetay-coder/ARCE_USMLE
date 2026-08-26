from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any

# Pesos canônicos FSRS v4.5 otimizados
WEIGHTS = [
    0.40255, 1.18385, 3.173, 15.69105,  # w0..w3 (Estabilidade inicial por grau 1..4)
    7.1949, 0.5345,                     # w4, w5 (Dificuldade inicial)
    1.4604, 0.0046,                     # w6, w7 (Atualização de dificuldade e reversão à média)
    1.54575, 0.1192, 1.01925,           # w8..w10 (Estabilidade em recall)
    1.9395, 0.11, 0.29605, 2.2698,      # w11..w14 (Estabilidade em lapse/Again)
    0.2315, 2.9898,                     # w15, w16 (Modificadores Hard e Easy)
]

FACTOR = 19.0 / 81.0  # Fator padrão FSRS v4.5/v5
DECAY = -0.5          # Potência de decaimento da retenção


class CardState(IntEnum):
    NEW = 0
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


@dataclass(frozen=True)
class RatingPreview:
    grade: int                    # 1: Again, 2: Hard, 3: Good, 4: Easy
    label: str                    # "Again", "Hard", "Good", "Easy"
    interval_display: str         # "<10m", "1d", "4d", "14d"
    interval_days: float          # Dias (ex: 0.007 para 10 min, 4.0 para 4 dias)
    new_stability: float          # S pós-avaliação
    new_difficulty: float         # D pós-avaliação
    new_state: CardState          # Estado resultante
    due_datetime: datetime        # Timestamp exato do próximo vencimento
    due_iso: str                  # ISO format string


@dataclass(frozen=True)
class FSRSCardTelemetry:
    current_retrievability: float # R atual (0.0 a 1.0)
    current_stability: float      # S atual em dias
    current_difficulty: float     # D atual (1.0 a 10.0)
    state: CardState              # Estado atual
    repetitions: int              # Total de revisões
    lapses: int                   # Total de esquecimentos
    elapsed_days: float           # Dias desde a última revisão


@dataclass(frozen=True)
class CardFSRSPreview:
    telemetry: FSRSCardTelemetry
    ratings: dict[int, RatingPreview]  # Mapeia 1..4 para seus respectivos previews


def calculate_retrievability(elapsed_days: float, stability: float) -> float:
    """Calcula a recuperabilidade R(t, S) em tempo real."""
    if stability <= 0:
        return 0.0
    if elapsed_days <= 0:
        return 1.0
    return math.pow(1.0 + FACTOR * (elapsed_days / stability), DECAY)


def calculate_interval(stability: float, desired_retention: float = 0.90) -> float:
    """Calcula o intervalo ótimo I(S, r) em dias com base na estabilidade e retenção desejada."""
    desired_retention = max(0.70, min(0.98, float(desired_retention)))
    if stability <= 0:
        return 1.0
    # Fórmula FSRS v4.5: I = (S / FACTOR) * (r^(1/DECAY) - 1) -> (81/19) * S * (r^(-2) - 1)
    interval = (1.0 / FACTOR) * stability * (math.pow(desired_retention, 1.0 / DECAY) - 1.0)
    return max(0.007, interval)  # Mínimo de ~10 minutos


def apply_fuzz(interval_days: float, grade: int, seed: int | None = None) -> float:
    """
    Aplica perturbação estocástica sutil (+/- 5%) em intervalos >= 3 dias
    para evitar o acúmulo de revisões em bloco no mesmo dia (efeito avalanche).
    """
    if interval_days < 2.5:
        return interval_days

    delta = 1.0 if interval_days < 7.0 else max(1.0, interval_days * 0.05)
    rng = random.Random(seed) if seed is not None else random.Random()
    fuzz = rng.uniform(-delta, delta)
    fuzzed = max(1.0, interval_days + fuzz)
    return round(fuzzed, 2)


def format_interval_human(days: float) -> str:
    """Formata o intervalo em representação humana concisa padrão Anki."""
    if days < 0.02:  # Menos de ~30 min
        return "<10m"
    if days < 0.08:  # ~1 hora
        return "<1h"
    if days < 1.0:
        hours = max(1, round(days * 24))
        return f"{hours}h"
    if days < 30.0:
        d = max(1, round(days))
        return f"{d}d"
    if days < 365.0:
        months = round(days / 30.0, 1)
        if months.is_integer():
            return f"{int(months)}m"
        return f"{months:.1f}m"
    years = round(days / 365.0, 1)
    if years.is_integer():
        return f"{int(years)}a"
    return f"{years:.1f}a"


def _initial_stability(grade: int) -> float:
    idx = max(0, min(3, grade - 1))
    return max(0.1, WEIGHTS[idx])


def _initial_difficulty(grade: int) -> float:
    d0 = WEIGHTS[4] - math.exp(WEIGHTS[5] * (grade - 1)) + 1.0
    return max(1.0, min(10.0, d0))


def initialize_difficulty_stability(grade: int) -> tuple[float, float]:
    """Inicialização padrão FSRS para a primeira revisão."""
    return _initial_difficulty(grade), _initial_stability(grade)


def _next_difficulty(current_d: float, grade: int) -> float:
    d0_good = _initial_difficulty(3)
    # Mean-reversion em direção à dificuldade média
    next_d = WEIGHTS[7] * d0_good + (1.0 - WEIGHTS[7]) * (current_d - WEIGHTS[6] * (grade - 3))
    return max(1.0, min(10.0, next_d))


def _next_recall_stability(current_d: float, current_s: float, r: float, grade: int) -> float:
    hard_penalty = WEIGHTS[15] if grade == 2 else 1.0
    easy_bonus = WEIGHTS[16] if grade == 4 else 1.0
    
    multiplier = 1.0 + math.exp(WEIGHTS[8]) * (11.0 - current_d) * math.pow(current_s, -WEIGHTS[9]) * (math.exp(WEIGHTS[10] * (1.0 - r)) - 1.0) * hard_penalty * easy_bonus
    return max(0.1, current_s * multiplier)


def _next_forget_stability(current_d: float, current_s: float, r: float) -> float:
    stab = WEIGHTS[11] * math.pow(current_d, -WEIGHTS[12]) * (math.pow(current_s + 1.0, WEIGHTS[13]) - 1.0) * math.exp(WEIGHTS[14] * (1.0 - r))
    return max(0.1, min(current_s, stab))


def calculate_card_preview(
    card: dict[str, Any],
    desired_retention: float = 0.90,
    now: datetime | None = None,
) -> CardFSRSPreview:
    """
    Calcula antecipadamente a telemetria e os 4 ramos de avaliação (Again, Hard, Good, Easy)
    para renderização dinâmica nos botões da interface.
    """
    now = now or datetime.now(timezone.utc)
    
    # Extrair parâmetros do card
    raw_s = card.get("stability")
    raw_d = card.get("difficulty")
    raw_reps = card.get("repetitions")
    raw_lapses = card.get("lapses")
    raw_state = card.get("state")
    
    stability = float(raw_s) if raw_s is not None else 1.0
    difficulty = float(raw_d) if raw_d is not None else 5.0
    reps = int(raw_reps) if raw_reps is not None else 0
    lapses = int(raw_lapses) if raw_lapses is not None else 0
    
    if raw_state is not None:
        try:
            state = CardState(int(raw_state))
        except (ValueError, TypeError):
            state = CardState.REVIEW if reps > 0 else CardState.NEW
    else:
        state = CardState.REVIEW if reps > 0 else CardState.NEW

    # Tempo decorrido
    last_review = card.get("last_review_at") or card.get("last_review")
    if last_review:
        try:
            cleaned_iso = str(last_review).replace("Z", "+00:00")
            if "T" not in cleaned_iso:
                cleaned_iso = f"{cleaned_iso}T00:00:00+00:00"
            last_dt = datetime.fromisoformat(cleaned_iso)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed_days = max(0.0, (now - last_dt).total_seconds() / 86400.0)
        except Exception:
            elapsed_days = 0.0
    else:
        elapsed_days = 0.0

    retrievability = calculate_retrievability(elapsed_days, stability)

    telemetry = FSRSCardTelemetry(
        current_retrievability=retrievability,
        current_stability=stability,
        current_difficulty=difficulty,
        state=state,
        repetitions=reps,
        lapses=lapses,
        elapsed_days=elapsed_days,
    )

    card_seed = int(card.get("id") or 1) + reps
    ratings: dict[int, RatingPreview] = {}
    labels = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}

    for grade in (1, 2, 3, 4):
        if reps == 0 or state == CardState.NEW:
            # Card Novo
            new_d = _initial_difficulty(grade)
            new_s = _initial_stability(grade)
            if grade == 1:
                new_state = CardState.LEARNING
                raw_interval = 0.007  # ~10 min
            elif grade == 2:
                new_state = CardState.LEARNING
                raw_interval = 1.0    # 1 dia
            elif grade == 3:
                new_state = CardState.REVIEW
                raw_interval = calculate_interval(new_s, desired_retention)
            else:  # Easy
                new_state = CardState.REVIEW
                raw_interval = max(3.0, calculate_interval(new_s, desired_retention) * 1.3)
        else:
            # Card em Revisão ou Reaprendizado
            new_d = _next_difficulty(difficulty, grade)
            if grade == 1:
                # Lapse / Again
                new_s = _next_forget_stability(difficulty, stability, retrievability)
                new_state = CardState.RELEARNING
                raw_interval = 0.007  # ~10 min no mesmo dia
            elif grade == 2:
                # Hard
                new_s = _next_recall_stability(difficulty, stability, retrievability, 2)
                new_state = CardState.REVIEW
                # Intervalo Hard é no mínimo 1 dia e no máximo 1.2x da estabilidade atual
                raw_interval = max(1.0, calculate_interval(new_s, desired_retention) * 0.8)
            elif grade == 3:
                # Good
                new_s = _next_recall_stability(difficulty, stability, retrievability, 3)
                new_state = CardState.REVIEW
                raw_interval = calculate_interval(new_s, desired_retention)
            else:
                # Easy
                new_s = _next_recall_stability(difficulty, stability, retrievability, 4)
                new_state = CardState.REVIEW
                raw_interval = calculate_interval(new_s, desired_retention)

        # Aplicar Fuzzing anti-avalanche em intervalos maiores
        fuzzed_days = apply_fuzz(raw_interval, grade, seed=card_seed + grade * 7) if raw_interval >= 2.5 else raw_interval
        due_dt = now + timedelta(days=fuzzed_days)

        ratings[grade] = RatingPreview(
            grade=grade,
            label=labels[grade],
            interval_display=format_interval_human(fuzzed_days),
            interval_days=round(fuzzed_days, 2),
            new_stability=round(new_s, 2),
            new_difficulty=round(new_d, 2),
            new_state=new_state,
            due_datetime=due_dt,
            due_iso=due_dt.isoformat(),
        )

    return CardFSRSPreview(telemetry=telemetry, ratings=ratings)


def calculate_fsrs(
    grade: int,
    difficulty: float,
    stability: float,
    elapsed_days: int | float,
    repetitions: int,
    lapses: int,
    desired_retention: float = 0.90,
) -> tuple[float, float, float, int, int, int]:
    """
    Interface canônica compatível com versões anteriores.
    Retorna: (difficulty, stability, retrievability, interval_days, repetitions, lapses)
    """
    card_dict = {
        "difficulty": difficulty,
        "stability": stability,
        "repetitions": repetitions,
        "lapses": lapses,
        "last_review_at": (datetime.now(timezone.utc) - timedelta(days=elapsed_days)).isoformat(),
    }
    preview = calculate_card_preview(card_dict, desired_retention=desired_retention)
    selected_branch = preview.ratings.get(grade, preview.ratings[3])
    
    new_reps = repetitions + 1
    new_lapses = lapses + (1 if grade == 1 else 0)
    interval_int = max(1, round(selected_branch.interval_days))

    return (
        selected_branch.new_difficulty,
        selected_branch.new_stability,
        preview.telemetry.current_retrievability,
        interval_int,
        new_reps,
        new_lapses,
    )
