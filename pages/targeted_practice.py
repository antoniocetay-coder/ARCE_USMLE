from __future__ import annotations

import json
import logging

from nicegui import run, ui

from ai.client import GeminiServiceError
from config import SISTEMAS_DISPONIVEIS
from core.exceptions import QuestionGenerationError
from core.question_generation_service import QuestionGenerationService
from pages.common import load_session, page_layout, save_session
from taxonomy import TAXONOMIA_COMPLETA

logger = logging.getLogger(__name__)


@ui.page("/targeted-practice")
def targeted_practice_page() -> None:
    with page_layout("Prática Direcionada", "/targeted-practice"):
        with ui.column().classes("w-full gap-1 mb-2"):
            ui.label("Prática Direcionada de Conceitos").classes("text-3xl font-extrabold text-slate-900 heading-font tracking-tight")
            ui.label("Gere questões clínicas customizadas em microtags focadas para reforçar pontos fracos.").classes("text-slate-500 font-medium text-sm")

        with ui.card().classes("study-card w-full max-w-3xl gap-4 my-2"):
            with ui.row().classes("items-center gap-3 border-b border-slate-100 pb-3"):
                ui.icon("track_changes", size="24px").classes("text-teal-700")
                ui.label("Configurar Foco Clínico").classes("font-bold text-slate-900 text-lg heading-font")

            # Wrong Answer Re-Test Banner
            from core.repositories.question_repository import QuestionRepository
            incorrect_rows = QuestionRepository().get_incorrect_questions(limit=30)
            incorrect_cnt = len(incorrect_rows)

            with ui.card().classes("w-full p-4 bg-rose-50/70 border border-rose-200 rounded-2xl gap-2 shadow-2xs"):
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("error_outline", size="22px").classes("text-rose-600")
                        with ui.column().classes("gap-0"):
                            ui.label("🚨 Desafio de Erros (Wrong Answer Re-Test)").classes("font-bold text-rose-950 text-sm")
                            ui.label(f"Você tem {incorrect_cnt} questão(ões) incorreta(s) salvas no seu histórico.").classes("text-xs text-rose-700 font-medium")

                    def start_error_retest() -> None:
                        if not incorrect_rows:
                            ui.notify("Excelente! Você não possui questões incorretas acumuladas.", type="positive")
                            return
                        retested = QuestionRepository().prepare_incorrect_for_restudy(limit=len(incorrect_rows))
                        queue_rows = [{"id": q["id"], "sistema": q["sistema"], "dificuldade": q["dificuldade"], "question_json": json.dumps(q)} for q in retested]
                        session = load_session()
                        QuestionGenerationService.populate_study_session(session, "🔥 Desafio de Erros", queue_rows)
                        save_session(session)
                        ui.notify(f"Iniciando treino de {len(queue_rows)} questões incorretas!", type="warning")
                        ui.navigate.to("/study")

                    ui.button("Re-testar Erros Agora", icon="local_fire_department", on_click=start_error_retest).props("color=negative size=sm").classes("rounded-xl font-bold")

            # Mastery Proof Test Banner
            from core.repositories.analytics_repository import AnalyticsRepository
            consolidated_tags = AnalyticsRepository().get_consolidated_tags()
            if consolidated_tags:
                with ui.card().classes("w-full p-4 bg-indigo-50/70 border border-indigo-200 rounded-2xl gap-2 shadow-2xs mt-2"):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("workspace_premium", size="22px").classes("text-indigo-600")
                            with ui.column().classes("gap-0"):
                                ui.label("🎓 Mastery Proof Test").classes("font-bold text-indigo-950 text-sm")
                                ui.label(f"Você tem {len(consolidated_tags)} tag(s) prontas para virar Mastered.").classes("text-xs text-indigo-700 font-medium")
                                
                        proof_tag_select = ui.select([t["tag"] for t in consolidated_tags], label="Escolha a Tag").classes("w-48")
                        if proof_tag_select.options:
                            proof_tag_select.value = proof_tag_select.options[0]
                            
                        async def start_proof_test() -> None:
                            if not proof_tag_select.value:
                                return
                            tag_to_prove = proof_tag_select.value
                            proof_btn.disable()
                            ui.notify(f"Gerando Proof Test (20 questões Difíceis) para {tag_to_prove}...", type="info")
                            
                            try:
                                # We need to find which system this tag belongs to
                                sys_for_tag = "General_Principles"
                                for s, d in TAXONOMIA_COMPLETA.items():
                                    if any(tag_to_prove in v for v in d.values() if isinstance(v, list)):
                                        sys_for_tag = s
                                        break
                                
                                rows = await run.io_bound(
                                    QuestionGenerationService().generate_study_plan_questions,
                                    [sys_for_tag], [tag_to_prove], "Hard",
                                    "2nd Order (Pathophysiology/Next Step in Management)", 20,
                                )
                                session = load_session()
                                QuestionGenerationService.populate_study_session(session, f"🏆 Proof Test: {tag_to_prove}", rows)
                                save_session(session)
                                ui.navigate.to("/study")
                            except Exception as e:
                                logger.exception("Failed to generate proof test")
                                ui.notify(f"Erro ao gerar Proof Test: {e}", type="negative")
                            finally:
                                proof_btn.enable()

                        proof_btn = ui.button("Iniciar Teste", icon="play_arrow", on_click=start_proof_test).props("color=indigo size=sm").classes("rounded-xl font-bold")

            with ui.column().classes("w-full gap-4 mt-2"):
                system = ui.select(SISTEMAS_DISPONIVEIS, value=SISTEMAS_DISPONIVEIS[0], label="Sistema Médico USMLE").classes("w-full")
                tag = ui.select([], label="Microtag de Especialidade Alvo").classes("w-full")

                # Obsidian Knowledge Base 54-Ontology & Node Grid Explorer
                from components.knowledge_card import render_knowledge_node_card
                from core.repositories.knowledge_repository import KnowledgeRepository
                repo = KnowledgeRepository()
                ontology_counts = repo.get_ontology_counts()
                ontology_options = sorted([k for k in ontology_counts.keys() if k])
                
                if ontology_options:
                    with ui.card().classes("w-full p-5 bg-slate-50/80 border border-slate-200 rounded-2xl gap-3 shadow-xs mt-3"):
                        with ui.row().classes("items-center justify-between w-full border-b border-slate-200/60 pb-3"):
                            with ui.row().classes("items-center gap-2.5"):
                                ui.icon("hub", size="24px").classes("text-sky-600")
                                with ui.column().classes("gap-0"):
                                    ui.label("🧠 Exploração Ontológica do Knowledge Vault").classes("font-extrabold text-slate-900 text-base heading-font")
                                    ui.label(f"{len(ontology_options)} ontologias ativas mapeando 8.044 nós médicos com RAG.").classes("text-xs text-slate-500 font-medium")

                        ontology_select = ui.select(ontology_options, value=ontology_options[0], label="Selecionar Categoria Ontológica (54 Tipos)").classes("w-full")
                        nodes_container = ui.column().classes("w-full gap-3 mt-2")

                        async def practice_specific_node(node) -> None:
                            ui.notify(f"Gerando questão clínica NBME (RAG) para o nó: {node.title}...", type="info")
                            try:
                                from config import SISTEMAS_DISPONIVEIS
                                cat = getattr(node, "folder_category", "")
                                sys_target = cat if cat in SISTEMAS_DISPONIVEIS else (system.value if system.value in SISTEMAS_DISPONIVEIS else "General_Principles")
                                rows = await run.io_bound(
                                    QuestionGenerationService().generate_study_plan_questions,
                                    [sys_target], [node.title], "Medium",
                                    "2nd Order (Pathophysiology/Next Step in Management)", 1,
                                )
                                session = load_session()
                                QuestionGenerationService.populate_study_session(session, f"🧠 RAG: {node.title}", rows)
                                save_session(session)
                                ui.navigate.to("/study")
                            except Exception as e:
                                logger.exception("Failed to generate node question")
                                ui.notify(f"Erro ao gerar questão RAG: {e}", type="negative")

                        def update_ontology_nodes() -> None:
                            nodes_container.clear()
                            if ontology_select.value:
                                nodes = repo.list_nodes_by_ontology(ontology_select.value, limit=6, exclude_orphans=True)
                                count = ontology_counts.get(ontology_select.value, 0)
                                with nodes_container:
                                    ui.label(f"Exibindo {len(nodes)} de {count} nós indexados para '{ontology_select.value}' (filtrando órfãos):").classes("text-xs font-bold text-slate-500 mb-1")
                                    for n in nodes:
                                        full_n = repo.get_node_by_id(n.node_id) or n
                                        render_knowledge_node_card(full_n, on_select=practice_specific_node)

                        ontology_select.on_value_change(update_ontology_nodes)
                        update_ontology_nodes()

            status = ui.label().classes("text-teal-700 text-xs font-semibold mt-1")


            def update_tags() -> None:
                taxonomy = TAXONOMIA_COMPLETA.get(system.value, {})
                tags = sorted({item for values in taxonomy.values() if isinstance(values, list) for item in values})
                tag.options = tags
                tag.value = tags[0] if tags else None
                tag.update()

            async def generate() -> None:
                if not tag.value:
                    ui.notify("Não há tags disponíveis para este sistema.", type="warning")
                    return
                generate_button.disable()
                status.set_text(f"Gerando 1 questão médica com Gemini para {system.value} ({tag.value})...")
                try:
                    rows = await run.io_bound(
                        QuestionGenerationService().generate_study_plan_questions,
                        [system.value], [tag.value], "Medium",
                        "2nd Order (Pathophysiology/Next Step in Management)", 1,
                    )
                    question = json.loads(rows[0]["question_json"])

                    # Populate current study session so the question can be answered immediately
                    session = load_session()
                    QuestionGenerationService.populate_study_session(session, f"Prática: {tag.value}", rows)
                    save_session(session)

                    result.clear()
                    with result:
                        ui.notify("Questão criada como pendente!", type="positive")
                        with ui.card().classes("w-full p-6 bg-slate-50 border border-slate-200 rounded-2xl gap-4 my-3 shadow-sm"):
                            with ui.row().classes("items-center justify-between"):
                                ui.label(f"{system.value} · {tag.value}").classes("bg-teal-100 text-teal-800 font-bold text-xs px-3 py-1 rounded-full")
                                ui.label("PRONTA PARA RESPONDER").classes("bg-emerald-600 text-white font-extrabold text-xs px-2.5 py-0.5 rounded")

                            ui.markdown(question["vignette"]).classes("text-slate-800 font-medium text-base leading-relaxed")

                            with ui.row().classes("w-full justify-between items-center mt-3 pt-3 border-t border-slate-200"):
                                ui.button("► Responder Esta Questão Agora", icon="play_arrow", on_click=lambda: ui.navigate.to("/study")).props("color=primary size=lg").classes("w-full rounded-xl font-bold py-3 shadow-md")


                except (QuestionGenerationError, GeminiServiceError) as error:
                    logger.exception("Targeted question generation failed")
                    ui.notify(str(error), type="negative")
                except Exception:
                    logger.exception("Unexpected targeted question generation failure")
                    ui.notify("Não foi possível gerar a questão. Verifique sua chave Gemini em Configurações.", type="negative")
                finally:
                    generate_button.enable()
                    status.set_text("")

            system.on_value_change(lambda _: update_tags())
            update_tags()

            generate_button = ui.button("Gerar Questão Focada", icon="rocket_launch", on_click=generate).props("color=primary size=lg").classes("w-full rounded-xl font-bold shadow-md mt-2")

        result = ui.column().classes("w-full max-w-3xl")
