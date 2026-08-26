from __future__ import annotations

import logging

from nicegui import ui

from config import SISTEMAS_DISPONIVEIS
from core.ai.engine import gerar_mnemonico_ia
from core.exceptions import TutorGenerationError
from core.repositories.mnemonic_repository import MnemonicRepository
from core.repositories.pearl_repository import PearlRepository
from pages.common import ai_is_configured, page_layout

logger = logging.getLogger(__name__)


@ui.page("/mnemonics")
def mnemonics_page() -> None:
    with page_layout("Mnemônicos & Pérolas", "/mnemonics"):
        with ui.column().classes("w-full gap-1 mb-2"):
            ui.label("Central de Mnemônicos & Pérolas High-Yield").classes("text-3xl font-extrabold text-slate-900 heading-font tracking-tight")
            ui.label("Pesquise por sintomas ou conceitos, gere mnemônicos via IA Gemini e gerencie seu acervo de memorização.").classes("text-slate-500 font-medium text-sm")

        # Top Control Panel: AI Generator & Manual Creation Tabs
        with ui.card().classes("study-card w-full p-6 gap-4 my-2 bg-gradient-to-r from-amber-50/60 via-white to-white border-amber-200/80"):
            with ui.tabs().classes("w-full") as tabs:
                tab_ai = ui.tab("⚡ Gerar Mnemônico com IA", icon="auto_awesome")
                tab_manual = ui.tab("✏️ Adicionar Manualmente", icon="add")
                tab_pearl = ui.tab("💎 Nova Pérola High-Yield", icon="diamond")

            with ui.tab_panels(tabs, value=tab_ai).classes("w-full bg-transparent p-0 mt-3"):
                # Tab 1: AI Generator
                with ui.tab_panel(tab_ai):
                    ui.label("Geração Inteligente via Gemini").classes("font-bold text-slate-900 text-sm mb-1")
                    ui.label("Informe qualquer patologia, sintoma ou mecanismo (ex: Feocromocitoma, Síndrome de Cushing, MUDPILES) para a IA criar uma regra de memorização.").classes("text-xs text-slate-500 mb-3")

                    with ui.row().classes("w-full gap-3 flex-wrap items-center"):
                        concept_input = ui.input(placeholder="Conceito médico (ex.: Cetoacidose Diabética, Tetralogia de Fallot)...").classes("flex-1 min-w-72")
                        estilo_select = ui.select(
                            ["🎨 Cena Visual (Dual-Coding)", "🔤 Acrônimo / Palavra-Chave", "🔗 Ponte Fonética"],
                            value="🎨 Cena Visual (Dual-Coding)",
                            label="Estilo Mnemônico",
                        ).classes("w-60")
                        ai_sistema_select = ui.select(SISTEMAS_DISPONIVEIS, value=SISTEMAS_DISPONIVEIS[0], label="Sistema Médico").classes("w-48")

                        async def generate_via_ai() -> None:
                            if not concept_input.value or not concept_input.value.strip():
                                ui.notify("Informe o conceito médico para a IA.", type="warning")
                                return
                            if not ai_is_configured():
                                ui.notify("Configure sua chave da API Gemini nas Configurações.", type="warning")
                                return

                            ai_btn.disable()
                            ui.notify(f"Gerando mnemônico ({estilo_select.value}) via IA...", type="info")
                            try:
                                from nicegui import run
                                from core.ai.mnemonics_generator import generate_advanced_mnemonic
                                result_json = await run.io_bound(generate_advanced_mnemonic, concept_input.value.strip(), estilo_select.value)
                                title = f"Mnemônico: {concept_input.value.strip()}"
                                
                                import json
                                parsed = json.loads(result_json)
                                fallback_content = f"### {parsed.get('anchor', '')}\n\n{parsed.get('bizarre_association', '')}\n\n"
                                for item in parsed.get('items', []):
                                    fallback_content += f"* **{item.get('initial')}** - {item.get('concept')}: {item.get('explanation')} {item.get('visual_cue')}\n"
                                
                                MnemonicRepository().salvar_mnemonico(title, fallback_content, ai_sistema_select.value, structured_data=result_json)
                                concept_input.value = ""
                                ui.notify("Mnemônico de alta retenção salvo!", type="positive")
                                render_list()
                            except (TutorGenerationError, Exception) as error:
                                ui.notify(str(error), type="negative")
                            finally:
                                ai_btn.enable()

                        ai_btn = ui.button("Gerar Mnemônico Científico", icon="auto_awesome", on_click=generate_via_ai).props("color=amber-9 size=md").classes("rounded-xl font-bold text-white shadow-sm")

                # Tab 2: Manual Creation
                with ui.tab_panel(tab_manual):
                    with ui.column().classes("w-full gap-3"):
                        with ui.row().classes("w-full gap-3 flex-wrap"):
                            title_input = ui.input(placeholder="Título do Mnemônico (ex.: MUDPILES)").classes("flex-1 min-w-60")
                            sistema_select = ui.select(SISTEMAS_DISPONIVEIS, value=SISTEMAS_DISPONIVEIS[0], label="Sistema").classes("w-48")
                        content_input = ui.textarea(placeholder="Conteúdo / Detalhamento do mnemônico...").classes("w-full")

                        def add_manual() -> None:
                            if not title_input.value or not content_input.value:
                                ui.notify("Preencha o título e o conteúdo.", type="warning")
                                return
                            MnemonicRepository().salvar_mnemonico(title_input.value, content_input.value, sistema_select.value)
                            title_input.value = ""
                            content_input.value = ""
                            ui.notify("Mnemônico salvo!", type="positive")
                            render_list()

                        ui.button("Salvar Mnemônico", icon="check", on_click=add_manual).props("color=primary").classes("rounded-xl font-bold")

                # Tab 3: New High-Yield Pearl
                with ui.tab_panel(tab_pearl):
                    with ui.column().classes("w-full gap-3"):
                        with ui.row().classes("w-full gap-3 flex-wrap items-center"):
                            pearl_input = ui.input(placeholder="Pérola High-Yield (ex.: 💎 Pérola: Na cetoacidose, a acidose é de ânion gap elevado)...").classes("flex-1 min-w-72")
                            pearl_sistema_select = ui.select(SISTEMAS_DISPONIVEIS, value=SISTEMAS_DISPONIVEIS[0], label="Sistema").classes("w-48")

                            def add_pearl() -> None:
                                if not pearl_input.value or not pearl_input.value.strip():
                                    ui.notify("Preencha a pérola.", type="warning")
                                    return
                                PearlRepository().salvar_perola(pearl_input.value.strip(), pearl_sistema_select.value)
                                pearl_input.value = ""
                                ui.notify("Pérola High-Yield salva!", type="positive")
                                render_list()

                            ui.button("Salvar Pérola", icon="diamond", on_click=add_pearl).props("color=indigo").classes("rounded-xl font-bold")

        # Interactive Search & Filter Bar
        with ui.card().classes("study-card w-full p-4 gap-3 my-2 bg-white border border-slate-200"):
            ui.label("🔍 Busca Semântica em Tempo Real & Filtros").classes("font-bold text-slate-800 text-xs uppercase tracking-wider")
            with ui.row().classes("w-full gap-3 flex-wrap items-center"):
                search_input = ui.input(
                    placeholder="Pesquisar por sintoma, doença, palavra-chave ou acrônimo...",
                ).props("clearable icon=search").classes("flex-1 min-w-72")

                sistema_filter = ui.select(
                    ["Todos os Sistemas"] + SISTEMAS_DISPONIVEIS,
                    value="Todos os Sistemas",
                    label="Sistema Médico",
                ).classes("w-52")

                type_filter = ui.select(
                    ["Todos", "Mnemônicos", "Pérolas High-Yield"],
                    value="Todos",
                    label="Tipo de Item",
                ).classes("w-44")

        # Dynamic Content List Container
        list_container = ui.column().classes("w-full gap-4 mt-2")

        def render_list() -> None:
            list_container.clear()

            raw_mnemonics = MnemonicRepository().get_todos_mnemonicos()
            raw_pearls = PearlRepository().get_todas_perolas()

            query = (search_input.value or "").strip().lower()
            selected_sys = sistema_filter.value
            selected_type = type_filter.value

            # Combine and filter items
            combined_items = []

            if selected_type in ("Todos", "Mnemônicos"):
                for m in raw_mnemonics:
                    combined_items.append({
                        "id": m["id"],
                        "kind": "mnemonic",
                        "title": m.get("title", "Mnemônico"),
                        "content": m.get("content", ""),
                        "structured_data": m.get("structured_data", ""),
                        "sistema": m.get("sistema", "General_Principles"),
                        "created_at": m.get("created_at", ""),
                    })

            if selected_type in ("Todos", "Pérolas High-Yield"):
                for p in raw_pearls:
                    combined_items.append({
                        "id": p["id"],
                        "kind": "pearl",
                        "title": "💎 Pérola High-Yield USMLE",
                        "content": p.get("pearl_text", ""),
                        "sistema": p.get("sistema", "General_Principles"),
                        "created_at": p.get("created_at", ""),
                    })

            # Apply filters
            filtered = []
            for item in combined_items:
                if selected_sys != "Todos os Sistemas" and item["sistema"] != selected_sys:
                    continue

                if query:
                    searchable_text = f"{item['title']} {item['content']} {item['sistema']}".lower()
                    if query not in searchable_text:
                        continue

                filtered.append(item)

            with list_container:
                ui.label(f"Exibindo {len(filtered)} de {len(combined_items)} item(ns) encontrado(s)").classes("text-xs font-bold text-slate-400 uppercase tracking-wider")

                if not filtered:
                    with ui.card().classes("study-card w-full text-center items-center py-12"):
                        ui.icon("search_off", size="48px").classes("text-slate-300 mb-2")
                        ui.label("Nenhum item encontrado").classes("text-xl font-bold text-slate-800 heading-font")
                        ui.label("Tente ajustar os termos da pesquisa ou os filtros selecionados.").classes("text-slate-500 text-sm")
                    return

                for item in filtered:
                    is_mnemonic = item["kind"] == "mnemonic"
                    card_border = "border-amber-200/80 bg-white" if is_mnemonic else "border-indigo-200/80 bg-indigo-50/30"
                    badge_color = "bg-amber-100 text-amber-900" if is_mnemonic else "bg-indigo-100 text-indigo-900"
                    icon_name = "lightbulb" if is_mnemonic else "diamond"
                    icon_color = "text-amber-500" if is_mnemonic else "text-indigo-600"

                    with ui.card().classes(f"study-card w-full p-5 gap-3 border shadow-xs relative {card_border}"):
                        with ui.row().classes("w-full justify-between items-center border-b border-slate-100 pb-2"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon(icon_name, size="20px").classes(icon_color)
                                ui.label(item["title"]).classes("font-extrabold text-slate-900 text-base heading-font")

                            with ui.row().classes("items-center gap-2"):
                                ui.label(item["sistema"].replace("_", " ")).classes(f"{badge_color} font-bold text-xs px-2.5 py-0.5 rounded-full uppercase")

                                if is_mnemonic:
                                    def make_delete(m_id: int):
                                        def _del() -> None:
                                            MnemonicRepository().deletar_mnemonico(m_id)
                                            ui.notify("Mnemônico excluído.", type="info")
                                            render_list()
                                        return _del

                                    ui.button(icon="delete", on_click=make_delete(item["id"])).props("flat color=rose size=sm").classes("rounded-lg")

                        if is_mnemonic:
                            # Rich View Container with Active Recall Toggle
                            view_container = ui.column().classes("w-full gap-2")

                            with view_container:
                                structured_raw = item.get("structured_data")
                                if structured_raw:
                                    import json
                                    try:
                                        data = json.loads(structured_raw)
                                        # Render Anchor & Story
                                        with ui.card().classes("w-full bg-amber-50/50 p-4 border border-amber-200/50"):
                                            ui.label(f"🎯 Âncora: {data.get('anchor', '')}").classes("font-extrabold text-amber-900 text-sm mb-1")
                                            ui.label(data.get("bizarre_association", "")).classes("text-slate-800 text-sm font-medium italic")
                                        
                                        # Active Recall Toggle State
                                        is_recall_mode = {"value": False}
                                        
                                        with ui.row().classes("w-full justify-between items-center mt-2"):
                                            ui.label("Itens do Mnemônico").classes("font-bold text-slate-700 text-xs uppercase tracking-wider")
                                            recall_switch = ui.switch("Treinar Memória (Active Recall)")
                                            recall_switch.classes("text-xs font-bold text-slate-500")
                                        
                                        items_col = ui.column().classes("w-full gap-2")
                                        
                                        def build_items(recall: bool):
                                            items_col.clear()
                                            with items_col:
                                                for i, m_item in enumerate(data.get("items", [])):
                                                    with ui.row().classes("w-full items-center gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100 hover:bg-slate-100 transition-colors"):
                                                        ui.label(m_item.get("visual_cue", "💡")).classes("text-2xl")
                                                        ui.label(m_item.get("initial", "")).classes("text-xl font-black text-amber-600 w-8 text-center")
                                                        
                                                        content_col = ui.column().classes("gap-0")
                                                        if recall:
                                                            with content_col:
                                                                ui.label("?").classes("font-bold text-slate-400 text-base")
                                                                ui.label("Passe o mouse para revelar").classes("text-xs text-slate-300 italic")
                                                                # Using tooltip for reveal
                                                                content_col.tooltip(f"{m_item.get('concept')}: {m_item.get('explanation')}")
                                                        else:
                                                            with content_col:
                                                                ui.label(m_item.get("concept", "")).classes("font-bold text-slate-800 text-base")
                                                                ui.label(m_item.get("explanation", "")).classes("text-sm text-slate-500")

                                        build_items(False)
                                        recall_switch.on_value_change(lambda e: build_items(e.value))
                                    except Exception as ex:
                                        ui.markdown(item["content"]).classes("text-slate-800 text-sm leading-relaxed w-full")
                                else:
                                    ui.markdown(item["content"]).classes("text-slate-800 text-sm leading-relaxed w-full")

                            # Edit Container (Hidden by default)
                            edit_container = ui.column().classes("w-full gap-2 hidden")
                            with edit_container:
                                content_area = ui.textarea(value=item["content"]).classes("w-full text-sm text-slate-800 font-medium")

                                def make_update(m_id: int, area, t_val: str):
                                    def _update() -> None:
                                        MnemonicRepository().atualizar_mnemonico(m_id, t_val, area.value)
                                        ui.notify("Mnemônico atualizado!", type="positive")
                                        render_list()
                                    return _update

                                ui.button("Salvar Alterações", icon="save", on_click=make_update(item["id"], content_area, item["title"])).props("flat color=primary size=sm").classes("font-bold text-xs border border-slate-200 rounded-lg w-fit")

                            def make_toggle(vc, ec):
                                def _toggle() -> None:
                                    vc.classes(toggle="hidden")
                                    ec.classes(toggle="hidden")
                                return _toggle

                            with ui.row().classes("w-full justify-end mt-1"):
                                ui.button("Editar Conteúdo", icon="edit", on_click=make_toggle(view_container, edit_container)).props("flat color=slate size=sm").classes("text-xs font-semibold")
                        else:
                            ui.markdown(item["content"]).classes("text-slate-800 text-sm font-semibold leading-relaxed")

        search_input.on_value_change(lambda _: render_list())
        sistema_filter.on_value_change(lambda _: render_list())
        type_filter.on_value_change(lambda _: render_list())

        render_list()
