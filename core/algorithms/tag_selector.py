from __future__ import annotations

from typing import Any, Protocol


class DiffusionEngineProtocol(Protocol):
    def diffuse(self, seed_heat: dict[str, float], steps: int = 3, alpha: float = 0.70) -> dict[str, float]: ...


class TagSelectionPolicyNetwork:
    """Rede de Seleção Adaptativa de Tags.

    Funde o vetor de energia da difusão ontológica (heat_vector) com a maestria BKT/FSRS (mastery_map)
    para produzir a lista otimizada de tags para estudo com intercalação inteligente.
    """

    def __init__(self, diffusion_engine: DiffusionEngineProtocol | None = None) -> None:
        self.diffusion_engine = diffusion_engine

    def select_study_tags(
        self,
        seed_heat: dict[str, float],
        mastery_map: dict[str, float],
        confusions: list[dict[str, Any]] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Seleciona as K melhores tags de estudo a partir da difusão e BKT."""
        if self.diffusion_engine:
            heat_vector = self.diffusion_engine.diffuse(seed_heat)
        else:
            heat_vector = dict(seed_heat)

        scored_candidates: list[dict[str, Any]] = []

        for tag, heat in heat_vector.items():
            mastery = mastery_map.get(tag, 0.15)
            # Formula: Priority Score = Heat * (1.5 - Mastery)
            priority_score = heat * (1.5 - mastery)

            # Assign priority label
            if heat >= 0.5 and mastery < 0.5:
                category = "CRITICAL_PREREQUISITE"
            elif heat >= 0.3:
                category = "HIGH_DIFFUSION_FOCUS"
            else:
                category = "SUPPORTING_CONCEPT"

            scored_candidates.append({
                "tag": tag,
                "score": round(priority_score, 4),
                "heat": heat,
                "mastery": round(mastery, 4),
                "category": category,
            })

        # Also consider direct confusion traps
        if confusions:
            for c in confusions:
                t1 = c.get("tag_correct")
                t2 = c.get("tag_confused")
                for t in (t1, t2):
                    if t and t not in heat_vector:
                        mastery = mastery_map.get(t, 0.15)
                        scored_candidates.append({
                            "tag": t,
                            "score": round(0.40 * (1.5 - mastery), 4),
                            "heat": 0.40,
                            "mastery": round(mastery, 4),
                            "category": "CONFUSION_TRAP",
                        })

        # Sort candidates by score descending
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Smart interleaving: filter out duplicate tags
        selected: list[dict[str, Any]] = []
        seen_tags: set[str] = set()

        for cand in scored_candidates:
            tag_name = cand["tag"].strip()
            if tag_name.lower() not in seen_tags and len(selected) < limit:
                seen_tags.add(tag_name.lower())
                selected.append(cand)

        return selected
