from __future__ import annotations

import json

from nicegui import ui

from config import SISTEMAS_DISPONIVEIS
from core.services.history_service import HistoryService
from core.services.study_workflow_service import StudyWorkflowService
from pages.common import page_layout


@ui.page("/history")
def history_page() -> None:
    with page_layout("Histórico", "/history"):
        with ui.column().classes("w-full gap-1 mb-2"):
            ui.label("Histórico de Questões & Caderno de Pérolas").classes("text-3xl font-extrabold text-slate-900 heading-font tracking-tight")
            ui.label("Revise o histórico de resoluções, justificativas e seu acervo de Pérolas High-Yield.").classes("text-slate-500 font-medium text-sm")

        workflow = StudyWorkflowService()
        pearls = workflow.get_saved_pearls()
        if pearls:
            with ui.card().classes("study-card w-full gap-3 my-2 bg-emerald-50/40 border-emerald-200"):
                with ui.row().classes("items-center justify-between border-b border-emerald-100 pb-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("diamond", size="22px").classes("text-emerald-600")
                        ui.label("Caderno de Pérolas High-Yield").classes("font-extrabold text-emerald-950 text-lg heading-font")
                    ui.label(f"{len(pearls)} Pérola(s) Salva(s)").classes("text-xs font-bold bg-emerald-100 text-emerald-900 px-3 py-1 rounded-full")

                with ui.column().classes("w-full gap-2 mt-1"):
                    for p in pearls:
                        with ui.card().classes("w-full p-3 bg-white border border-emerald-200 rounded-xl gap-1 shadow-2xs"):
                            ui.label(p["sistema"].replace("_", " ")).classes("text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded uppercase tracking-wider w-fit")
                            ui.markdown(p["pearl_text"]).classes("text-xs text-slate-800 font-medium")

        with ui.card().classes("study-card w-full gap-4 my-2"):
            with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                filter_select = ui.select(["Todos os Sistemas", *SISTEMAS_DISPONIVEIS], value="Todos os Sistemas", label="Filtrar por Sistema Médico").classes("w-full max-w-md")
            
            content = ui.column().classes("w-full gap-3 mt-2")

            def render() -> None:
                content.clear()
                items = HistoryService().answered_questions()
                if filter_select.value != "Todos os Sistemas":
                    items = [item for item in items if item["sistema"] == filter_select.value]
                
                with content:
                    ui.label(f"Exibindo {len(items)} questão(ões) respondida(s)").classes("text-xs font-bold text-slate-400 uppercase tracking-wider")
                    if not items:
                        with ui.column().classes("w-full text-center py-8 border border-dashed border-slate-200 rounded-xl items-center"):
                            ui.icon("history", size="40px").classes("text-slate-300 mb-1")
                            ui.label("Nenhuma questão encontrada para o filtro selecionado.").classes("text-slate-500 text-sm")
                        return

                    for row in items:
                        q_raw = row.get("question_json", "{}")
                        data = json.loads(q_raw) if isinstance(q_raw, str) else (q_raw or {})
                        if not isinstance(data, dict):
                            data = {}
                        is_correct = bool(row.get("answered_correctly"))
                        icon_name = "check_circle" if is_correct else "cancel"
                        icon_color = "text-emerald-600" if is_correct else "text-rose-600"
                        row_sys = str(row.get("sistema") or "General_Principles").replace("_", " ")
                        row_dif = str(row.get("dificuldade") or "Medium")
                        title = f"{row_sys} · Dificuldade: {row_dif}"

                        with ui.expansion(title, icon=icon_name).classes("w-full bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm"):
                            with ui.column().classes("p-4 w-full gap-3"):
                                with ui.row().classes("w-full justify-between items-center border-b border-slate-100 pb-2"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon(icon_name, size="20px").classes(icon_color)
                                        ui.label("Acerto" if is_correct else "Erro").classes("font-bold text-xs uppercase " + ("text-emerald-700" if is_correct else "text-rose-700"))

                                    ui.label(f"Respondido em: {row.get('answered_at', row.get('created_at', ''))}").classes("text-xs text-slate-400 font-medium")

                                ui.markdown(str(data.get("vignette", ""))).classes("text-slate-800 text-sm leading-relaxed font-medium")

                                ui.separator().classes("my-1")
                                ui.label("Opções e Gabarito:").classes("font-bold text-slate-900 text-xs uppercase tracking-wider")
                                options = data.get("options") if isinstance(data.get("options"), list) else []
                                correct_ans = str(data.get("correct", "A")).strip().upper()[:1]
                                for option in options:
                                    is_correct_opt = str(option).startswith(correct_ans)
                                    opt_style = "bg-emerald-50 border-emerald-300 text-emerald-950 font-bold" if is_correct_opt else "bg-slate-50 border-slate-200 text-slate-700"
                                    ui.label(str(option)).classes(f"text-xs p-2.5 rounded-lg border w-full {opt_style}")

                                if data.get('educational_objective'):
                                    with ui.card().classes("w-full p-3 bg-indigo-50 border border-indigo-150 rounded-lg mt-2"):
                                        ui.label("🎯 Objetivo Educacional").classes("font-bold text-indigo-950 text-xs uppercase")
                                        ui.markdown(str(data.get('educational_objective', ''))).classes("text-indigo-900 text-xs mt-0.5")

            filter_select.on_value_change(lambda _: render())
            render()
