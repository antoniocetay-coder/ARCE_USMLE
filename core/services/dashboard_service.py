from __future__ import annotations

from typing import Any

import config
from ai.settings import load_ai_settings
from core.algorithms.scheduler import build_study_plans, create_study_queue
from core.repositories.analytics_repository import AnalyticsRepository
from core.repositories.flashcard_repository import FlashcardRepository
from core.repositories.question_repository import QuestionRepository
from taxonomy import TAXONOMIA_COMPLETA


class DashboardService:
    """Application boundary consumed by NiceGUI dashboard callbacks."""

    def __init__(
        self,
        questions: QuestionRepository | None = None,
        flashcards: FlashcardRepository | None = None,
        analytics: AnalyticsRepository | None = None,
    ) -> None:
        self.questions = questions or QuestionRepository(config.DB_PATH)
        self.flashcards = flashcards or FlashcardRepository(config.DB_PATH)
        self.analytics = analytics or AnalyticsRepository(config.DB_PATH)

    def metrics(self) -> tuple[int, int, int]:
        due = len(self.flashcards.get_due_flashcards())
        pending = len(self.questions.get_pending_questions())
        systems = len(self.analytics.get_system_stats())
        return due, pending, systems

    def create_queue(self, mode: str) -> list[dict[str, Any]]:
        from core.algorithms.discrimination_drill import DiscriminationDrillService
        drill_service = DiscriminationDrillService(self.questions.path)

        if mode in ("ErroBook", "Caderno de Erros"):
            import json
            incorrect = self.questions.prepare_incorrect_for_restudy(10)
            rows = []
            for item in incorrect:
                if "question_json" not in item:
                    item_dict = dict(item)
                    q_json = json.dumps(item_dict, ensure_ascii=False)
                    row = {
                        "id": item["id"],
                        "sistema": item.get("sistema", "General_Principles"),
                        "dificuldade": item.get("dificuldade", "Medium"),
                        "question_json": q_json,
                        "status": "pending",
                    }
                else:
                    row = item
                rows.append({"type": "question", "item": row, "item_id": f"question:{row['id']}", "source": "caderno_de_erros"})
            return rows

        if mode in ("Drills", "Discriminação", "Discriminacao"):
            drills = drill_service.get_drills(limit=10)
            drill_dicts = [
                {
                    "id": d.id,
                    "concept_a": d.concept_a,
                    "concept_b": d.concept_b,
                    "prompt_clue": d.prompt_clue,
                    "correct_choice": d.correct_choice,
                    "pivot_explanation": d.pivot_explanation,
                    "sistema": d.sistema,
                    "tags": d.tags,
                }
                for d in drills
            ]
            return [
                {"type": "drill", "item": d, "item_id": f"drill:{d['id']}", "source": "discrimination_drill"}
                for d in drill_dicts
            ]

        # For Interleaved and standard modes
        drills = [
            {
                "id": d.id,
                "concept_a": d.concept_a,
                "concept_b": d.concept_b,
                "prompt_clue": d.prompt_clue,
                "correct_choice": d.correct_choice,
                "pivot_explanation": d.pivot_explanation,
                "sistema": d.sistema,
                "tags": d.tags,
            }
            for d in drill_service.get_drills(limit=5)
        ]
        return [
            {"type": item.item_type, "item": item.payload, "item_id": item.item_id, "source": item.source}
            for item in create_study_queue(mode, self.flashcards.get_due_flashcards(), self.questions.get_pending_questions(), drills)
        ]



    def study_plans(self) -> list[dict[str, Any]]:
        import random
        from core.algorithms.ontology_brain import OntologyBrain
        from core.repositories.knowledge_repository import KnowledgeRepository
        from core.services.ontology_vault_service import OntologyVaultService

        model = load_ai_settings().question_model
        knowledge_repo = KnowledgeRepository(self.questions.path)
        vault_categories = OntologyVaultService(knowledge_repo).get_vault_categories()

        # Tag-level mastery map from BKT / tag_stats
        tag_stats = self.analytics.get_tag_stats()
        mastery_map = {
            tag: float(data.get("mastery_prob") or (data["correct"] / data["total"] if data["total"] else 0.15))
            for tag, data in tag_stats.items()
        }
        confusions = self.get_confusions()

        brain = OntologyBrain(knowledge_repo)
        recommendations = brain.recommend_study_tags(mastery_map, confusions, limit=12)
        rec_tags = [r["tag"] for r in recommendations] if recommendations else []

        # If recommendations are few or empty, sample dynamically from the 8,000+ vault nodes across categories
        if len(rec_tags) < 12:
            all_summary = knowledge_repo.get_all_nodes_summary()
            if all_summary:
                # Prioritize unstudied nodes (all_summary is list[str])
                unstudied = [node_title for node_title in all_summary if node_title not in mastery_map]
                sample_pool = unstudied if len(unstudied) >= 12 else all_summary
                random_picks = random.sample(sample_pool, min(12 - len(rec_tags), len(sample_pool)))
                for pick in random_picks:
                    if pick not in rec_tags:
                        rec_tags.append(pick)

        # Fallback if knowledge repo is empty
        if not rec_tags:
            rec_tags = ["Acute myocardial infarction", "Atropine", "Diabetes mellitus", "Sickle cell anemia"]

        cat_1 = vault_categories[0] if len(vault_categories) > 0 else "General_Principles"
        cat_2 = vault_categories[1] if len(vault_categories) > 1 else "Renal"
        cat_3 = vault_categories[2] if len(vault_categories) > 2 else "Cardiovascular"

        plans = [
            {
                "titulo": "🚨 Plano Causa Raiz (Difusão Ontológica)",
                "sistemas": f"{cat_1} • {cat_2}",
                "desc": "Foco nos pré-requisitos essenciais identificados pela Rede de Difusão Ontológica.",
                "tags": rec_tags[:4],
                "difficulty": "Medium",
                "cognitive_order": "2nd Order (Pathophysiology/Next Step in Management)",
                "quantity": 5,
                "question_model": model,
                "icon": "auto_awesome",
                "icon_cls": "bg-rose-100 text-rose-700",
                "badge": "Prioridade Alta",
                "badge_cls": "bg-rose-100 text-rose-800",
                "time": "~12 min",
            },
            {
                "titulo": "🏗️ Plano Consolidação do Vault",
                "sistemas": f"{cat_2} • {cat_3}",
                "desc": "Treino balanceado entre conceitos em consolidação e novos nós do Obsidian Vault.",
                "tags": rec_tags[4:8] if len(rec_tags) >= 8 else rec_tags[:4],
                "difficulty": "Medium",
                "cognitive_order": "2nd Order (Pathophysiology/Next Step in Management)",
                "quantity": 5,
                "question_model": model,
                "icon": "hub",
                "icon_cls": "bg-sky-100 text-sky-700",
                "badge": "Recomendado",
                "badge_cls": "bg-sky-100 text-sky-800",
                "time": "~15 min",
            },
            {
                "titulo": "🧭 Plano Expansão Ontológica",
                "sistemas": f"{cat_3} • {cat_1}",
                "desc": "Exploração de tópicos avançados e armadilhas de distratores frequentes.",
                "tags": rec_tags[8:12] if len(rec_tags) >= 12 else rec_tags[:4],
                "difficulty": "Medium",
                "cognitive_order": "2nd Order (Pathophysiology/Next Step in Management)",
                "quantity": 5,
                "question_model": model,
                "icon": "explore",
                "icon_cls": "bg-purple-100 text-purple-700",
                "badge": "Desafio",
                "badge_cls": "bg-purple-100 text-purple-800",
                "time": "~15 min",
            },
        ]
        return plans

    def get_confusions(self) -> list[dict[str, Any]]:
        return self.analytics.get_global_confusions()

