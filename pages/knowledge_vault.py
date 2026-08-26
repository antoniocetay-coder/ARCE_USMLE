from __future__ import annotations

import math
import logging

from nicegui import run, ui

from components.knowledge_card import render_knowledge_node_card
from core.ai.rag_service import RAGService
from core.question_generation_service import QuestionGenerationService
from core.repositories.knowledge_repository import KnowledgeRepository
from core.services.ontology_vault_service import OntologyVaultService
from pages.common import load_session, page_layout, save_session

logger = logging.getLogger(__name__)

PAGE_SIZE = 20


@ui.page("/knowledge-vault")
def knowledge_vault_page() -> None:
    with page_layout("Knowledge Vault", "/knowledge-vault"):
        repo = KnowledgeRepository()
        vault_service = OntologyVaultService(repo)
        
        # State variables for filters and pagination
        state = {
            "current_page": 1,
            "total_count": 0,
            "total_pages": 1,
            "search_query": "",
            "category": "Todas as Categorias",
            "ontology_type": "Todos os Tipos",
        }

        # Hero Header Section
        with ui.column().classes("w-full gap-2 mb-4"):
            with ui.row().classes("items-center justify-between w-full flex-wrap gap-4"):
                with ui.row().classes("items-center gap-3"):
                    with ui.row().classes("w-12 h-12 rounded-2xl bg-sky-100 text-sky-700 items-center justify-center font-bold border border-sky-200 shadow-sm"):
                        ui.icon("hub", size="30px")
                    with ui.column().classes("gap-0"):
                        ui.label("Obsidian Knowledge Vault (RAG & Ontologias)").classes("text-3xl font-extrabold text-slate-900 heading-font tracking-tight")
                        ui.label("Acervo oficial de conhecimento médico do seu Vault com fundamentação RAG.").classes("text-slate-500 font-medium text-sm")

        # Vault Overview Metric Cards Banner
        categories_list = vault_service.get_vault_categories()
        ontology_types_list = vault_service.get_all_ontology_types()

        with ui.row().classes("w-full gap-4 my-2 flex-wrap"):
            with ui.card().classes("study-card flex-1 min-w-48 bg-gradient-to-r from-sky-900 to-slate-900 text-white border border-sky-800/40 p-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("inventory_2", size="24px").classes("text-sky-300")
                    with ui.column().classes("gap-0"):
                        ui.label("8.046").classes("text-2xl font-extrabold text-white heading-font")
                        ui.label("Nós Médicos no Vault").classes("text-xs text-sky-200/80 font-bold")

            with ui.card().classes("study-card flex-1 min-w-48 bg-white border border-slate-200 p-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("account_tree", size="24px").classes("text-teal-600")
                    with ui.column().classes("gap-0"):
                        ui.label(str(len(categories_list))).classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Domínios / Pastas").classes("text-xs text-slate-500 font-bold")

            with ui.card().classes("study-card flex-1 min-w-48 bg-white border border-slate-200 p-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("category", size="24px").classes("text-purple-600")
                    with ui.column().classes("gap-0"):
                        ui.label(str(len(ontology_types_list))).classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Tipos de Ontologia").classes("text-xs text-slate-500 font-bold")

            with ui.card().classes("study-card flex-1 min-w-48 bg-white border border-slate-200 p-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("share", size="24px").classes("text-amber-600")
                    with ui.column().classes("gap-0"):
                        ui.label("1.786").classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Arestas Ontológicas").classes("text-xs text-slate-500 font-bold")

        # Filters and Live Search Controls Card
        with ui.card().classes("w-full p-6 bg-white border border-slate-200 rounded-3xl shadow-sm gap-4 my-3"):
            ui.label("Filtros & Busca no Acervo").classes("text-sm font-extrabold text-slate-900 heading-font uppercase tracking-wider border-b border-slate-100 pb-2")
            
            with ui.row().classes("w-full gap-4 items-center flex-wrap"):
                search_input = ui.input(placeholder="Pesquisar por título, código ou conceito (ex: STEMI, GFR, Atropine)...").classes("flex-1 min-w-72 text-base")
                
                cat_options = ["Todas as Categorias"] + categories_list
                selected_cat = ui.select(cat_options, value="Todas as Categorias", label="Categoria do Vault").classes("w-64")
                
                ont_options = ["Todos os Tipos"] + ontology_types_list
                selected_ont = ui.select(ont_options, value="Todos os Tipos", label="Tipo de Ontologia").classes("w-56")

            with ui.row().classes("w-full justify-between items-center pt-2"):
                ui.button("Limpar Filtros", icon="clear_all", on_click=lambda: clear_filters()).props("flat color=slate size=sm").classes("font-semibold text-xs")
                ui.button("Buscar no Vault", icon="search", on_click=lambda: trigger_search()).props("color=sky size=md").classes("rounded-xl font-bold px-6 shadow-sm")

        # Counter and Pagination Control Bar (Top & Bottom)
        counter_label = ui.label("Carregando acervo...").classes("text-xs font-extrabold text-slate-600 uppercase tracking-wider my-1")
        
        pagination_top = ui.row().classes("w-full justify-between items-center py-2")
        nodes_grid = ui.element("div").classes("w-full grid grid-cols-1 md:grid-cols-2 gap-4 my-2")
        pagination_bottom = ui.row().classes("w-full justify-center items-center py-4 border-t border-slate-200/60 mt-4")

        async def practice_node(node) -> None:
            ui.notify(f"Gerando questão clínica NBME (RAG) para: {node.title}...", type="info")
            try:
                from config import SISTEMAS_DISPONIVEIS
                cat = getattr(node, "folder_category", "")
                sys_target = cat if cat in SISTEMAS_DISPONIVEIS else "General_Principles"
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
                ui.notify(f"Erro ao gerar questão: {e}", type="negative")

        def load_current_page() -> None:
            offset = (state["current_page"] - 1) * PAGE_SIZE
            total, nodes = repo.filter_nodes_paginated(
                query=state["search_query"],
                category=state["category"],
                ontology_type=state["ontology_type"],
                offset=offset,
                limit=PAGE_SIZE,
            )
            state["total_count"] = total
            state["total_pages"] = max(1, math.ceil(total / PAGE_SIZE))

            # Counter display text
            if total == 0:
                counter_label.set_text("Nenhum nó de conhecimento encontrado.")
            else:
                start_idx = offset + 1
                end_idx = min(offset + PAGE_SIZE, total)
                counter_label.set_text(f"Exibindo {start_idx} – {end_idx} de {total:,} nós de conhecimento médico:")

            # Render Nodes Grid
            nodes_grid.clear()
            with nodes_grid:
                if not nodes:
                    with ui.card().classes("col-span-full p-8 text-center items-center bg-slate-50 border border-slate-200 rounded-2xl w-full"):
                        ui.icon("search_off", size="40px").classes("text-slate-300 mb-2")
                        ui.label("Nenhum Nó Encontrado").classes("text-lg font-bold text-slate-800")
                        ui.label("Tente ajustar os termos de busca ou selecionar outra categoria.").classes("text-xs text-slate-400")
                else:
                    for n in nodes:
                        full_n = repo.get_node_by_id(n.node_id) or n
                        render_knowledge_node_card(full_n, on_select=practice_node)

            render_pagination_controls()

        def render_pagination_controls() -> None:
            for container in (pagination_top, pagination_bottom):
                container.clear()
                with container:
                    with ui.row().classes("items-center gap-2 flex-wrap justify-center w-full"):
                        p = state["current_page"]
                        tot = state["total_pages"]

                        def go_to(page_num: int) -> None:
                            state["current_page"] = max(1, min(page_num, state["total_pages"]))
                            load_current_page()

                        btn_first = ui.button("⏮ Primeira", on_click=lambda: go_to(1)).props("flat color=sky size=sm").classes("font-bold text-xs")
                        btn_prev = ui.button("◀ Anterior", on_click=lambda: go_to(p - 1)).props("flat color=sky size=sm").classes("font-bold text-xs")
                        
                        ui.label(f"Página {p} de {tot:,}").classes("text-xs font-extrabold text-slate-800 bg-sky-50 px-4 py-1.5 rounded-xl border border-sky-200")

                        btn_next = ui.button("Próxima ▶", on_click=lambda: go_to(p + 1)).props("flat color=sky size=sm").classes("font-bold text-xs")
                        btn_last = ui.button("Última ⏭", on_click=lambda: go_to(tot)).props("flat color=sky size=sm").classes("font-bold text-xs")

                        if p <= 1:
                            btn_first.disable()
                            btn_prev.disable()
                        if p >= tot:
                            btn_next.disable()
                            btn_last.disable()

        def trigger_search() -> None:
            state["search_query"] = search_input.value or ""
            state["category"] = selected_cat.value or "Todas as Categorias"
            state["ontology_type"] = selected_ont.value or "Todos os Tipos"
            state["current_page"] = 1
            load_current_page()

        def clear_filters() -> None:
            search_input.value = ""
            selected_cat.value = "Todas as Categorias"
            selected_ont.value = "Todos os Tipos"
            trigger_search()

        search_input.on("keydown.enter", trigger_search)
        selected_cat.on_value_change(lambda e: trigger_search())
        selected_ont.on_value_change(lambda e: trigger_search())

        load_current_page()
