from __future__ import annotations

from collections import deque
from typing import Any, Protocol


class KnowledgeRepositoryProtocol(Protocol):
    def get_prerequisite_sources(self, target_tag: str) -> list[str]: ...
    def get_dependent_targets(self, source_tag: str) -> list[str]: ...
    def get_ontology_relations(self, tag: str) -> list[dict[str, str]]: ...


_CACHED_ENGINES: dict[str, Any] = {}


def _get_cached_diffusion_engine(repository: Any) -> Any:
    repo_path = str(getattr(repository, "path", None) or "default")
    if repo_path not in _CACHED_ENGINES:
        from core.algorithms.diffusion_engine import OntologyDiffusionEngine
        nodes_summary = getattr(repository, "get_all_nodes_summary", lambda: [])()
        edges_summary = getattr(repository, "get_all_edges_summary", lambda: [])()
        if nodes_summary and edges_summary:
            _CACHED_ENGINES[repo_path] = OntologyDiffusionEngine(nodes_summary, edges_summary)
    return _CACHED_ENGINES.get(repo_path)


class OntologyBrain:
    """Orquestrador Cognitivo Ontológico.

    Navega pelo grafo de conhecimento médico para identificar
    pré-requisitos, causas raízes e montar planos de estudo adaptativos.
    """

    def __init__(self, repository: KnowledgeRepositoryProtocol | None = None) -> None:
        if repository is None:
            from core.repositories.knowledge_repository import KnowledgeRepository
            self.repository: KnowledgeRepositoryProtocol = KnowledgeRepository()
        else:
            self.repository = repository

    def get_prerequisites(self, tag: str, max_depth: int = 2) -> list[str]:
        """Retorna os pré-requisitos diretos e indiretos de uma tag (busca em largura)."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(tag.strip(), 0)])
        prereqs: list[str] = []

        while queue:
            current_tag, current_depth = queue.popleft()
            if current_depth >= max_depth:
                continue

            sources = self.repository.get_prerequisite_sources(current_tag)

            for src in sources:
                if src not in visited and src.lower() != tag.lower():
                    visited.add(src)
                    prereqs.append(src)
                    queue.append((src, current_depth + 1))

        return prereqs

    def get_dependent_topics(self, tag: str, max_depth: int = 2) -> list[str]:
        """Retorna os tópicos avançados que dependem da tag fornecida."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(tag.strip(), 0)])
        dependents: list[str] = []

        while queue:
            current_tag, current_depth = queue.popleft()
            if current_depth >= max_depth:
                continue

            targets = self.repository.get_dependent_targets(current_tag)

            for tgt in targets:
                if tgt not in visited and tgt.lower() != tag.lower():
                    visited.add(tgt)
                    dependents.append(tgt)
                    queue.append((tgt, current_depth + 1))

        return dependents

    def get_clinical_relations(self, tag: str) -> dict[str, list[str]]:
        """Retorna todas as conexões clínicas de um nó organizadas por relação."""
        result: dict[str, list[str]] = {
            "PREREQUISITE_FOR": [],
            "CAUSES": [],
            "MANIFESTS_AS": [],
            "TREATED_BY": [],
        }

        rows = self.repository.get_ontology_relations(tag)
        for r in rows:
            rel = r["relation"]
            src = r["source"]
            tgt = r["target"]

            if rel in result:
                other = tgt if src.lower() == tag.strip().lower() else src
                if other not in result[rel]:
                    result[rel].append(other)

        return result

    def get_root_cause_tags(self, mastery_map: dict[str, float], threshold: float = 0.50) -> list[dict[str, Any]]:
        """Identifica quais falhas em tópicos avançados são causadas por lacunas em pré-requisitos."""
        root_causes: list[dict[str, Any]] = []

        failing_tags = [tag for tag, score in mastery_map.items() if score < threshold]

        for target_tag in failing_tags:
            prereqs = self.get_prerequisites(target_tag, max_depth=2)
            unmastered_prereqs = [
                p for p in prereqs
                if mastery_map.get(p, 0.15) < threshold
            ]

            if unmastered_prereqs:
                root_causes.append({
                    "failing_topic": target_tag,
                    "target_mastery": mastery_map.get(target_tag, 0.15),
                    "prerequisites": unmastered_prereqs,
                    "recommended_action": f"Revisar {', '.join(unmastered_prereqs[:3])} antes de refazer {target_tag}.",
                })

        return root_causes

    def recommend_study_tags(
        self,
        mastery_map: dict[str, float],
        confusions: list[dict[str, Any]] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Orquestra as melhores tags a serem trabalhadas via Difusão de Calor Ontológico."""
        from core.algorithms.tag_selector import TagSelectionPolicyNetwork

        engine = _get_cached_diffusion_engine(self.repository)

        seed_heat: dict[str, float] = {}
        for tag, score in mastery_map.items():
            if score < 0.50:
                seed_heat[tag] = round(1.5 - score, 2)

        policy = TagSelectionPolicyNetwork(engine)
        results = policy.select_study_tags(seed_heat, mastery_map, confusions=confusions, limit=limit)
        return [
            {
                "tag": r["tag"],
                "priority": r["category"],
                "reason": f"Calor de Difusão: {r['heat']:.2f} · Maestria: {r['mastery']:.0%}",
                "mastery": r["mastery"],
            }
            for r in results
        ]
