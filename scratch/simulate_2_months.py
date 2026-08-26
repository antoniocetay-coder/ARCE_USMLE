from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Setup paths to import project modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from core.algorithms.diffusion_engine import OntologyDiffusionEngine
from core.algorithms.mastery import update_bkt
from core.algorithms.ontology_brain import OntologyBrain
from core.algorithms.tag_selector import TagSelectionPolicyNetwork
from core.repositories.application_repository import ApplicationRepository
from core.repositories.knowledge_repository import KnowledgeRepository


def run_60_day_simulation():
    print("=" * 70)
    print("🔬 SIMULAÇÃO DE 60 DIAS DE USO REAL DO ARC-e USMLE (ISOLADA & SEGURA)")
    print("=" * 70)

    # 1. Carregar nós e arestas reais da base em modo READ-ONLY
    real_db_path = PROJECT_ROOT / "usmle_data.db"
    if not real_db_path.exists():
        print("Base usmle_data.db não encontrada.")
        return

    # Conectar em modo estritamente read-only via URI
    ro_uri = f"file:{real_db_path.as_posix()}?mode=ro"
    real_conn = sqlite3.connect(ro_uri, uri=True)
    real_conn.row_factory = sqlite3.Row

    nodes_summary = [
        {"node_id": r["node_id"], "title": r["title"], "ontology_type": r["ontology_type"], "folder_category": r["folder_category"]}
        for r in real_conn.execute("SELECT node_id, title, ontology_type, folder_category FROM knowledge_nodes").fetchall()
    ]
    edges_summary = [
        {"source": r["source"], "relation": r["relation"], "target": r["target"]}
        for r in real_conn.execute("SELECT source, relation, target FROM ontology_edges").fetchall()
    ]
    real_conn.close()

    print(f"📦 Grafo Ontológico Carregado: {len(nodes_summary)} nós médicos | {len(edges_summary)} arestas ontológicas")

    # 2. Criar banco temporário isolado em memória RAM para a simulação
    sim_db = sqlite3.connect(":memory:")
    sim_db.row_factory = sqlite3.Row
    sim_db.execute("CREATE TABLE tag_stats (tag TEXT PRIMARY KEY, correct INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0, mastery_prob REAL)")
    sim_db.execute("CREATE TABLE confusions (tag_correct TEXT NOT NULL, tag_confused TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (tag_correct, tag_confused))")
    sim_db.execute("CREATE TABLE question_history (day INTEGER, tag TEXT, sistema TEXT, correct INTEGER)")
    sim_db.execute("CREATE TABLE flashcard_reviews (day INTEGER, tag TEXT, rating INTEGER)")

    node_ids = [n["node_id"] for n in nodes_summary]
    diffusion_engine = OntologyDiffusionEngine(node_ids, edges_summary)
    policy_network = TagSelectionPolicyNetwork(diffusion_engine)

    # Catálogo de tags por sistema
    system_to_tags: dict[str, list[str]] = defaultdict(list)
    tag_to_system: dict[str, str] = {}
    for n in nodes_summary:
        sys_cat = n["folder_category"] or "General_Principles"
        system_to_tags[sys_cat].append(n["node_id"])
        tag_to_system[n["node_id"]] = sys_cat

    all_tag_ids = [n["node_id"] for n in nodes_summary]

    # Estado de maestria do aluno simulado
    mastery_map: dict[str, float] = {}
    studied_tags_over_time: list[str] = []
    daily_logs: list[dict] = []

    # Parâmetros da simulação
    DAYS = 60
    QUESTIONS_PER_DAY = 15
    STUDENT_BASE_ACCURACY = 0.70  # 70% de acerto base

    print(f"⏱️ Simulando {DAYS} dias de estudo diário ({QUESTIONS_PER_DAY} questões/dia)...")

    for day in range(1, DAYS + 1):
        # 1. Obter recomendações adaptativas baseadas no estado atual do aluno
        seed_heat: dict[str, float] = {}
        for tag, score in mastery_map.items():
            if score < 0.50:
                seed_heat[tag] = round(1.5 - score, 2)

        confusions_rows = [
            {"tag_correct": r["tag_correct"], "tag_confused": r["tag_confused"], "count": r["count"]}
            for r in sim_db.execute("SELECT tag_correct, tag_confused, count FROM confusions").fetchall()
        ]

        # Se houver sementes de erro, difunde calor; senão explora tags novas
        recommended = policy_network.select_study_tags(seed_heat, mastery_map, confusions=confusions_rows, limit=6)
        rec_tags = [r["tag"] for r in recommended]

        # Montar a fila de estudo do dia: 60% focado em gaps/difusão, 40% em exploração de novos nós
        day_study_tags = []
        if rec_tags:
            day_study_tags.extend(rec_tags[:min(4, len(rec_tags))])

        while len(day_study_tags) < QUESTIONS_PER_DAY:
            # Explorar nós ainda não dominados ou aleatórios
            unseen = [t for t in all_tag_ids if t not in mastery_map]
            if unseen:
                candidate = random.choice(unseen)
            else:
                candidate = random.choice(all_tag_ids)
            if candidate not in day_study_tags:
                day_study_tags.append(candidate)

        # 2. Simular resolução das questões
        day_correct = 0
        for tag in day_study_tags:
            studied_tags_over_time.append(tag)
            current_mastery = mastery_map.get(tag, 0.15)

            # Probabilidade de acerto influenciada pela maestria
            prob_correct = min(0.95, max(0.20, current_mastery * 0.8 + STUDENT_BASE_ACCURACY * 0.2))
            is_correct = 1 if random.random() < prob_correct else 0

            if is_correct:
                day_correct += 1
            else:
                # Gerar confusão com nó vizinho
                prereqs = [e["target"] for e in edges_summary if e["source"] == tag]
                if prereqs:
                    confused = random.choice(prereqs)
                    sim_db.execute(
                        "INSERT INTO confusions (tag_correct, tag_confused, count) VALUES (?, ?, 1) ON CONFLICT(tag_correct, tag_confused) DO UPDATE SET count = count + 1",
                        (tag, confused),
                    )

            # Atualizar BKT
            conf_level = "Certeza Absoluta" if is_correct and random.random() > 0.3 else "Dúvida entre 2"
            new_mastery = update_bkt(current_mastery, is_correct=bool(is_correct), confidence=conf_level, difficulty="Médio")
            mastery_map[tag] = new_mastery

            sistema = tag_to_system.get(tag, "General_Principles")
            sim_db.execute("INSERT INTO question_history VALUES (?, ?, ?, ?)", (day, tag, sistema, is_correct))

        daily_logs.append({
            "day": day,
            "accuracy": day_correct / QUESTIONS_PER_DAY,
            "unique_tags_today": len(set(day_study_tags)),
            "total_mastered": sum(1 for m in mastery_map.values() if m >= 0.75),
            "total_in_progress": sum(1 for m in mastery_map.values() if 0.20 <= m < 0.75),
            "total_struggling": sum(1 for m in mastery_map.values() if m < 0.20),
        })

    # Análise Estatística dos 60 Dias
    total_questions = len(studied_tags_over_time)
    tag_counts = Counter(studied_tags_over_time)
    unique_tags_count = len(tag_counts)
    most_common_10 = tag_counts.most_common(10)

    # Cobertura por Sistema
    system_counts = Counter(tag_to_system.get(t, "General_Principles") for t in studied_tags_over_time)

    # Entropia de Distribuição (Shannon Entropy)
    import math
    probs = [count / total_questions for count in tag_counts.values()]
    entropy = -sum(p * math.log2(p) for p in probs)
    max_entropy = math.log2(unique_tags_count) if unique_tags_count > 1 else 1
    normalized_diversity = entropy / max_entropy if max_entropy > 0 else 0

    print("\n" + "=" * 70)
    print("📊 RESULTADOS ESTATÍSTICOS DA SIMULAÇÃO (60 DIAS)")
    print("=" * 70)
    print(f"• Total de Questões Resolvidas: {total_questions}")
    print(f"• Total de Nós Médicos Distintos Estudados: {unique_tags_count} (de {len(nodes_summary)} nós totais)")
    print(f"• Índice de Diversidade / Entropia: {normalized_diversity:.1%} (Quanto mais próximo de 100%, mais equilibrada a distribuição)")
    print(f"• Média de repetição por nó: {total_questions / unique_tags_count:.2f}x ao longo de 2 meses")

    print("\n🏷️ TOP 10 TEMAS MAIS FREQUENTES NA SIMULAÇÃO:")
    for tag, cnt in most_common_10:
        print(f"   - {tag}: {cnt} ocorrências ({cnt/total_questions:.1%}) · Maestria Final: {mastery_map.get(tag, 0):.0%}")

    print("\n🏥 DISTRIBUIÇÃO POR SISTEMA:")
    for sys_name, cnt in system_counts.most_common():
        print(f"   - {sys_name}: {cnt} questões ({cnt/total_questions:.1%})")

    print("\n📈 EVOLUÇÃO TEMPORAL (A CADA 15 DIAS):")
    for d in [1, 15, 30, 45, 60]:
        log = daily_logs[d - 1]
        print(f"   Dia {d:02d}: Acurácia Diária = {log['accuracy']:.0%} | Dominados (≥75%) = {log['total_mastered']} | Em Progresso = {log['total_in_progress']}")

    # Diagnóstico da sensação do usuário
    print("\n" + "=" * 70)
    print("🔍 DIAGNÓSTICO: VOCÊ ESTÁ CERTO OU ERRADO?")
    print("=" * 70)
    
    return {
        "unique_tags": unique_tags_count,
        "total_nodes": len(nodes_summary),
        "diversity": normalized_diversity,
        "top_tags": most_common_10,
        "system_counts": dict(system_counts),
        "total_questions": total_questions,
    }


if __name__ == "__main__":
    run_60_day_simulation()
