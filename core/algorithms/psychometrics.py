from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class MurphyDecomposition:
    brier_score: float
    reliability: float
    resolution: float
    uncertainty: float
    ece: float
    mce: float
    overconfidence: float
    underconfidence: float
    calibration_grade: str
    calibration_color: str
    n_samples: int


@dataclass(frozen=True)
class USMLEContinuousPrediction:
    theta: float
    coverage_factor: float
    step1_pass_prob: float
    step1_pass_prob_display: str
    step2ck_predicted_score: int
    step2ck_ci_lower: int
    step2ck_ci_upper: int
    step2ck_ci_display: str
    sem: float
    readiness_label: str
    readiness_color: str
    total_answered: int


class PsychometricsEngine:
    CONFIDENCE_PROBS = {
        "Certeza Absoluta": 0.95,
        "Certeza": 0.95,
        "Dúvida entre 2": 0.55,
        "Média": 0.55,
        "Média Dúvida": 0.55,
        "Chute Cego": 0.20,
        "Chute": 0.20,
    }

    MU_LOG_TIME = 4.22  # ln(68s)
    SIGMA_LOG_TIME = 0.45

    @classmethod
    def classify_latency_and_cognition(
        cls, response_time_sec: float, is_correct: bool, confidence: str
    ) -> tuple[float, str]:
        t = max(1.0, float(response_time_sec))
        z_time = (math.log(t) - cls.MU_LOG_TIME) / cls.SIGMA_LOG_TIME

        if t < 12.0 or z_time < -2.0:
            state = "rapid_guess" if not is_correct else "heuristic_guess"
        elif z_time <= -0.6 and is_correct and confidence in ("Certeza", "Certeza Absoluta"):
            state = "diagnostic_fluency"
        elif z_time > 1.8:
            state = "cognitive_stalling"
        else:
            state = "analytical_deliberation"

        return round(z_time, 3), state

    @classmethod
    def compute_murphy_and_ece(cls, rows: Sequence[dict[str, Any]]) -> MurphyDecomposition:
        if not rows:
            return MurphyDecomposition(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "Sem dados", "slate", 0)

        bins: dict[float, list[float]] = {0.95: [], 0.55: [], 0.20: []}
        all_outcomes: list[float] = []

        for r in rows:
            conf_str = str(r.get("confidence_level") or "")
            prob = cls.CONFIDENCE_PROBS.get(conf_str, 0.55)
            target_bin = min(bins.keys(), key=lambda b: abs(b - prob))
            outcome = 1.0 if r.get("answered_correctly") in (1, True, "1") else 0.0
            bins[target_bin].append(outcome)
            all_outcomes.append(outcome)

        n_total = len(all_outcomes)
        if n_total == 0:
            return MurphyDecomposition(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "Sem dados", "slate", 0)

        o_bar = sum(all_outcomes) / n_total
        uncertainty = o_bar * (1.0 - o_bar)

        reliability = 0.0
        resolution = 0.0
        ece = 0.0
        mce = 0.0
        overconfidence = 0.0
        underconfidence = 0.0
        brier_sq_errors = []

        for f_k, outcomes in bins.items():
            n_k = len(outcomes)
            if n_k == 0:
                continue
            o_bar_k = sum(outcomes) / n_k
            gap = f_k - o_bar_k

            reliability += (n_k / n_total) * (gap ** 2)
            resolution += (n_k / n_total) * ((o_bar_k - o_bar) ** 2)
            ece += (n_k / n_total) * abs(gap)
            mce = max(mce, abs(gap))

            if gap > 0:
                overconfidence += (n_k / n_total) * gap
            else:
                underconfidence += (n_k / n_total) * abs(gap)

            for o_i in outcomes:
                brier_sq_errors.append((f_k - o_i) ** 2)

        brier_score = sum(brier_sq_errors) / n_total if brier_sq_errors else 0.0

        if brier_score < 0.12 and ece < 0.10:
            grade = "Calibração Excepcional 🎯"
            color = "emerald"
        elif brier_score < 0.19 and ece < 0.18:
            grade = "Boa Calibração 👍"
            color = "teal"
        elif brier_score < 0.26:
            grade = "Calibração Moderada ⚠️"
            color = "amber"
        else:
            grade = "Ilusão de Competência 🚨"
            color = "rose"

        return MurphyDecomposition(
            brier_score=round(brier_score, 4),
            reliability=round(reliability, 4),
            resolution=round(resolution, 4),
            uncertainty=round(uncertainty, 4),
            ece=round(ece, 4),
            mce=round(mce, 4),
            overconfidence=round(overconfidence, 4),
            underconfidence=round(underconfidence, 4),
            calibration_grade=grade,
            calibration_color=color,
            n_samples=n_total,
        )

    @classmethod
    def predict_usmle(
        cls,
        total_questions: int,
        correct_questions: int,
        system_counts: dict[str, int],
        fsrs_retention: float = 0.90,
    ) -> USMLEContinuousPrediction:
        n = total_questions
        if n == 0:
            return USMLEContinuousPrediction(
                theta=0.0,
                coverage_factor=0.0,
                step1_pass_prob=50.0,
                step1_pass_prob_display="50%",
                step2ck_predicted_score=210,
                step2ck_ci_lower=194,
                step2ck_ci_upper=250,
                step2ck_ci_display="194 - 250",
                sem=20.0,
                readiness_label="Sem dados suficientes",
                readiness_color="slate",
                total_answered=0,
            )

        p_raw = correct_questions / n
        n_0 = 120.0
        w_n = n / (n + n_0)
        p_adj = w_n * p_raw + (1.0 - w_n) * 0.60
        p_adj = max(0.05, min(0.95, p_adj))

        theta = math.log(p_adj / (1.0 - p_adj))

        all_systems = [
            "General_Principles", "Cardiovascular", "Pulmonology", "Gastroenterology",
            "Renal", "Neurology", "Hematology", "Endocrine", "Musculoskeletal",
            "Dermatology", "Psychiatry", "Reproductive_OB_GYN", "Ophthalmology",
            "ENT", "Public_Health_Sciences", "Microbiology"
        ]
        s_counts = [system_counts.get(s, 0) for s in all_systems]
        t_sys = sum(s_counts) + len(all_systems)
        entropy = 0.0
        for sc in s_counts:
            p_s = (sc + 1) / t_sys
            entropy -= p_s * math.log(p_s)
        max_entropy = math.log(len(all_systems))
        coverage_entropy = entropy / max_entropy if max_entropy > 0 else 1.0

        solid_systems = sum(1 for sc in s_counts if sc >= 10)
        system_ratio = solid_systems / float(len(all_systems))
        coverage_factor = round(0.60 * coverage_entropy + 0.40 * system_ratio, 3)

        theta_pass = -0.42  # ~60% passing mark
        sem_theta = 1.20 / math.sqrt(n * max(0.20, coverage_factor) + 10.0)
        sigma_exam = 0.35
        denom = math.sqrt(sigma_exam ** 2 + sem_theta ** 2)
        z_step1 = (theta * (0.50 + 0.50 * coverage_factor) - theta_pass) / denom
        pass_prob_raw = 0.5 * (1.0 + math.erf(z_step1 / math.sqrt(2.0)))
        step1_pass_prob = max(1.0, min(99.0, pass_prob_raw * 100.0))

        score_point = 248.0 + 16.5 * (theta * (0.60 + 0.40 * coverage_factor))
        step2ck_score = int(round(max(194.0, min(295.0, score_point))))

        sem_asymptotic = 4.2
        sem = math.sqrt(sem_asymptotic ** 2 + (90.0 ** 2) / (n * max(0.15, coverage_factor) + 5.0))
        sem = round(sem, 2)

        ci_margin = 1.96 * sem
        ci_lower = max(194, int(round(step2ck_score - ci_margin)))
        ci_upper = min(300, int(round(step2ck_score + ci_margin)))

        if step1_pass_prob >= 95.0 and step2ck_score >= 245:
            label, color = "Excelente — Desempenho no Top Decil 🏆", "emerald"
        elif step1_pass_prob >= 85.0 and step2ck_score >= 230:
            label, color = "Sólido — Faixa Competitiva para Residência 🩺", "teal"
        elif step1_pass_prob >= 70.0:
            label, color = "Moderado — Reforce Lacunas Sistêmicas 📈", "amber"
        else:
            label, color = "Zona de Risco — Volume Adicional Necessário 🚨", "rose"

        return USMLEContinuousPrediction(
            theta=round(theta, 3),
            coverage_factor=coverage_factor,
            step1_pass_prob=round(step1_pass_prob, 1),
            step1_pass_prob_display=f"{step1_pass_prob:.0f}%",
            step2ck_predicted_score=step2ck_score,
            step2ck_ci_lower=ci_lower,
            step2ck_ci_upper=ci_upper,
            step2ck_ci_display=f"{ci_lower} - {ci_upper}",
            sem=sem,
            readiness_label=label,
            readiness_color=color,
            total_answered=n,
        )
