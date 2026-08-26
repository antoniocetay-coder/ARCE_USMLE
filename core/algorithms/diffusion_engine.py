from __future__ import annotations

from typing import Any, Protocol


class OntologyRepositoryProtocol(Protocol):
    def get_all_nodes_summary(self) -> list[dict[str, str]]: ...
    def get_all_edges_summary(self) -> list[dict[str, str]]: ...
    def get_global_confusions() -> list[dict[str, Any]]: ...


WEIGHT_MAP = {
    "PREREQUISITE_FOR": 0.85,  # Retro-propagação para causa raiz (target -> source)
    "CAUSES": 0.60,           # Propagação direta para etiologia (source -> target)
    "MANIFESTS_AS": 0.40,     # Propagação direta para sintomas (source -> target)
    "TREATED_BY": 0.30,       # Propagação para terapêutica (source -> target)
}


class OntologyDiffusionEngine:
    """Motor de Difusão de Calor Ontológico (Graph Heat Diffusion).

    Navega e propaga energia de dúvida/erro pela malha ontológica
    respeitando ponderação de arestas e normalização de grau.
    """

    def __init__(
        self,
        nodes: list[str] | None = None,
        edges: list[dict[str, str]] | None = None,
        confusions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.node_to_idx: dict[str, int] = {}
        self.idx_to_node: dict[int, str] = {}
        self.adjacency: dict[int, list[tuple[int, float]]] = {}
        self.degree: dict[int, float] = {}

        if nodes and edges:
            self.build_graph(nodes, edges, confusions or [])

    def build_graph(
        self,
        nodes: list[str],
        edges: list[dict[str, str]],
        confusions: list[dict[str, Any]],
    ) -> None:
        """Constrói a estrutura de adjacência ponderada do grafo."""
        self.node_to_idx.clear()
        self.idx_to_node.clear()
        self.adjacency.clear()
        self.degree.clear()

        # Map node titles/IDs to 0-indexed integers
        for idx, node in enumerate(nodes):
            n_clean = node.strip()
            self.node_to_idx[n_clean] = idx
            self.node_to_idx[n_clean.lower()] = idx
            self.idx_to_node[idx] = n_clean
            self.adjacency[idx] = []
            self.degree[idx] = 0.0

        # Build confusion boost dictionary
        confusion_boost: set[tuple[str, str]] = set()
        for c in confusions:
            t1 = str(c.get("tag_correct", "")).strip().lower()
            t2 = str(c.get("tag_confused", "")).strip().lower()
            if t1 and t2:
                confusion_boost.add((t1, t2))
                confusion_boost.add((t2, t1))

        # Populate weighted directed adjacency list
        for edge in edges:
            src = str(edge.get("source", "")).strip()
            rel = str(edge.get("relation", "")).strip()
            tgt = str(edge.get("target", "")).strip()

            base_w = WEIGHT_MAP.get(rel, 0.35)

            # High prerequisite backward diffusion (target -> source)
            if rel == "PREREQUISITE_FOR":
                s_idx = self.node_to_idx.get(tgt.lower())
                t_idx = self.node_to_idx.get(src.lower())
            else:
                s_idx = self.node_to_idx.get(src.lower())
                t_idx = self.node_to_idx.get(tgt.lower())

            if s_idx is not None and t_idx is not None and s_idx != t_idx:
                # Add confusion boost if user confused these concepts
                w = base_w
                if (src.lower(), tgt.lower()) in confusion_boost:
                    w += 0.30

                self.adjacency[s_idx].append((t_idx, w))
                self.degree[s_idx] += w

    def diffuse(
        self,
        seed_heat: dict[str, float],
        steps: int = 3,
        alpha: float = 0.70,
    ) -> dict[str, float]:
        """Propaga o calor injetado (seed_heat) pelo grafo durante 'steps' iterações.

        Retorna um dicionário {node_title: heat_score}.
        """
        num_nodes = len(self.idx_to_node)
        if num_nodes == 0:
            return {}

        # Vector h_0
        h_0 = [0.0] * num_nodes
        for tag, heat in seed_heat.items():
            idx = self.node_to_idx.get(tag.strip().lower())
            if idx is not None:
                h_0[idx] = max(0.0, float(heat))

        h_current = list(h_0)

        for _ in range(steps):
            h_next = [0.0] * num_nodes
            for u in range(num_nodes):
                u_heat = h_current[u]
                if u_heat <= 1e-6:
                    continue

                neighbors = self.adjacency.get(u, [])
                u_deg = self.degree.get(u, 1.0)
                if u_deg <= 0.0:
                    u_deg = 1.0

                for v, w in neighbors:
                    # Degree normalized heat transfer
                    transferred = u_heat * (w / u_deg)
                    h_next[v] += transferred

            # Apply convex combination: h_{t+1} = alpha * h_next + (1 - alpha) * h_0
            for i in range(num_nodes):
                h_current[i] = (alpha * h_next[i]) + ((1.0 - alpha) * h_0[i])

        # Return heat scores dictionary
        result: dict[str, float] = {}
        for idx, heat in enumerate(h_current):
            if heat > 1e-4:
                node_name = self.idx_to_node[idx]
                result[node_name] = round(heat, 4)

        return result
