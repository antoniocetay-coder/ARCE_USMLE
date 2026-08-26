from __future__ import annotations

from pathlib import Path
from typing import Any

from core.repositories.database import connection


import config


class AnalyticsRepository:
    def __init__(self, path: Path | str | None = None):
        self.path = path if path is not None else config.DB_PATH

    def get_tag_stats(self) -> dict[str, dict[str, Any]]:
        with connection(self.path) as conn:
            rows = conn.execute("SELECT tag, correct, total, mastery_prob FROM tag_stats").fetchall()
        return {row["tag"]: {"correct": row["correct"], "total": row["total"], "mastery_prob": row["mastery_prob"]} for row in rows}

    def get_system_stats(self) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT sistema, SUM(answered_correctly) AS acertos, COUNT(*) AS total FROM questions WHERE status='answered' GROUP BY sistema")]

    def get_metacognition_stats(self) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT confidence_level, answered_correctly, COUNT(*) AS qtd FROM questions WHERE status='answered' AND confidence_level IS NOT NULL GROUP BY confidence_level, answered_correctly")]

    def get_time_stats(self) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT sistema, answered_correctly, AVG(response_time) AS avg_time FROM questions WHERE status='answered' AND response_time IS NOT NULL GROUP BY sistema, answered_correctly")]

    def get_fsrs_forecast(self) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT due, COUNT(*) AS qtd FROM srs_state WHERE object_type='flashcard' GROUP BY due ORDER BY due")]

    def get_global_confusions(self) -> list[dict[str, Any]]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT tag_correct, tag_confused, count FROM confusions ORDER BY count DESC LIMIT 20")]

    def get_metacognitive_calibration(self) -> dict[str, Any]:
        from core.algorithms.psychometrics import PsychometricsEngine
        with connection(self.path) as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT confidence_level, answered_correctly, response_time FROM questions WHERE status='answered' AND confidence_level IS NOT NULL"
            ).fetchall()]

        murphy = PsychometricsEngine.compute_murphy_and_ece(rows)

        overconfidence_cnt = sum(
            1 for r in rows
            if str(r.get("confidence_level")) in ("Certeza", "Certeza Absoluta")
            and r.get("answered_correctly") in (0, False, "0")
        )
        underconfidence_cnt = sum(
            1 for r in rows
            if str(r.get("confidence_level")) in ("Chute", "Chute Cego")
            and r.get("answered_correctly") in (1, True, "1")
        )

        return {
            "brier_score": murphy.brier_score,
            "reliability": murphy.reliability,
            "resolution": murphy.resolution,
            "uncertainty": murphy.uncertainty,
            "ece": murphy.ece,
            "mce": murphy.mce,
            "overconfidence_error": murphy.overconfidence,
            "underconfidence_error": murphy.underconfidence,
            "calibration_grade": murphy.calibration_grade,
            "calibration_color": murphy.calibration_color,
            "overconfidence_count": overconfidence_cnt,
            "underconfidence_count": underconfidence_cnt,
            "total_analyzed": murphy.n_samples,
        }

    def get_usmle_pass_prediction(self) -> dict[str, Any]:
        from core.algorithms.psychometrics import PsychometricsEngine
        with connection(self.path) as conn:
            total_q = conn.execute("SELECT COUNT(*) as cnt FROM questions WHERE status = 'answered'").fetchone()["cnt"]
            correct_q = conn.execute("SELECT COUNT(*) as cnt FROM questions WHERE status = 'answered' AND answered_correctly = 1").fetchone()["cnt"]
            accuracy = (correct_q / total_q) if total_q > 0 else 0.0

            sys_rows = conn.execute("SELECT sistema, COUNT(*) as cnt FROM questions WHERE status = 'answered' GROUP BY sistema").fetchall()
            system_counts = {r["sistema"]: r["cnt"] for r in sys_rows}
            systems_cnt = len(system_counts)

            # FSRS total cards reviewed
            try:
                srs_count = conn.execute("SELECT COUNT(*) as cnt FROM srs_state").fetchone()["cnt"]
            except Exception:
                srs_count = 0
            avg_retention = 0.90 if srs_count > 0 else 0.85

            pred = PsychometricsEngine.predict_usmle(
                total_questions=total_q,
                correct_questions=correct_q,
                system_counts=system_counts,
                fsrs_retention=avg_retention,
            )

            readiness_score = int(round((0.50 * accuracy + 0.30 * avg_retention + 0.20 * min(1.0, systems_cnt / 16.0)) * 100))

            return {
                "readiness_score": readiness_score,
                "pass_probability": pred.step1_pass_prob_display,
                "step1_pass_prob": pred.step1_pass_prob_display,
                "step1_pass_prob_raw": pred.step1_pass_prob,
                "estimated_score_range": pred.step2ck_ci_display,
                "step2ck_predicted_score": pred.step2ck_predicted_score,
                "step2ck_score_ci": pred.step2ck_ci_display,
                "step2ck_ci_lower": pred.step2ck_ci_lower,
                "step2ck_ci_upper": pred.step2ck_ci_upper,
                "sem": pred.sem,
                "theta": pred.theta,
                "coverage_factor": pred.coverage_factor,
                "status_label": pred.readiness_label,
                "status_color": pred.readiness_color,
                "total_answered": total_q,
                "accuracy_pct": int(round(accuracy * 100)),
                "fsrs_retention_pct": int(round(avg_retention * 100)),
                "systems_covered": systems_cnt,
            }

    def get_user_streak_data(self) -> dict[str, Any]:
        from datetime import datetime, timedelta, timezone
        with connection(self.path) as conn:
            q_counts = conn.execute(
                "SELECT date(answered_at) as dt, COUNT(*) as cnt FROM questions WHERE answered_at IS NOT NULL GROUP BY date(answered_at)"
            ).fetchall()
            f_counts = conn.execute(
                "SELECT date(last_review) as dt, COUNT(*) as cnt FROM srs_state WHERE last_review IS NOT NULL GROUP BY date(last_review)"
            ).fetchall()

            activity_map: dict[str, int] = {}
            for r in q_counts:
                if r["dt"]:
                    activity_map[r["dt"]] = activity_map.get(r["dt"], 0) + r["cnt"]
            for r in f_counts:
                if r["dt"]:
                    activity_map[r["dt"]] = activity_map.get(r["dt"], 0) + r["cnt"]

            today_date = datetime.now(timezone.utc).date()
            today_str = today_date.strftime("%Y-%m-%d")

            streak = 0
            studied_today = today_str in activity_map

            if studied_today:
                streak += 1
                check_date = today_date - timedelta(days=1)
            else:
                check_date = today_date - timedelta(days=1)

            while True:
                dt_str = check_date.strftime("%Y-%m-%d")
                if dt_str in activity_map:
                    streak += 1
                    check_date -= timedelta(days=1)
                else:
                    break

            monday = today_date - timedelta(days=today_date.weekday())
            week_dots = []
            labels = ["S", "T", "Q", "Q", "S", "S", "D"]
            for i in range(7):
                day_str = (monday + timedelta(days=i)).strftime("%Y-%m-%d")
                week_dots.append({
                    "label": labels[i],
                    "date": day_str,
                    "active": day_str in activity_map,
                    "count": activity_map.get(day_str, 0)
                })

            return {
                "streak": streak,
                "studied_today": studied_today,
                "today_count": activity_map.get(today_str, 0),
                "week_dots": week_dots,
                "activity_map": activity_map,
            }

    def get_top_confounders(self, tag: str, limit: int = 3) -> list[str]:
        with connection(self.path) as conn:
            return [row["tag_confused"] for row in conn.execute("SELECT tag_confused FROM confusions WHERE tag_correct=? ORDER BY count DESC LIMIT ?", (tag, limit)).fetchall()]

    def get_consolidated_tags(self) -> list[dict]:
        with connection(self.path) as conn:
            return [dict(row) for row in conn.execute("SELECT tag, mastery_prob FROM tag_stats WHERE mastery_prob >= 0.65 AND mastery_prob < 0.90 ORDER BY mastery_prob DESC").fetchall()]
