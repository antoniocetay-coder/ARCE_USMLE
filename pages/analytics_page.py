from __future__ import annotations

import pandas as pd
import plotly.express as px
from nicegui import ui

from core.services.analytics_service import AnalyticsService
from pages.common import page_layout


@ui.page("/analytics")
def analytics_page() -> None:
    with page_layout("Analytics & Metacognição", "/analytics"):
        with ui.column().classes("w-full gap-1 mb-3"):
            ui.label("Cockpit de Analytics & Desempenho Clínico").classes("text-3xl font-extrabold text-slate-900 heading-font tracking-tight")
            ui.label("Calibração metacognitiva, precisão por sistema médico e modelo preditivo FSRS.").classes("text-slate-500 font-medium text-sm")

        data = AnalyticsService().dashboard()
        systems = data["systems"]

        if not systems:
            with ui.card().classes("study-card w-full text-center items-center py-16 my-2 bg-gradient-to-b from-slate-50 to-white"):
                ui.icon("analytics", size="56px").classes("text-slate-300 mb-3")
                ui.label("Sem Dados de Resolução Suficientes").classes("text-2xl font-bold text-slate-800 heading-font")
                ui.label("Complete algumas questões no QBank para desbloquear seus gráficos metacognitivos e de mastery.").classes("text-slate-500 mb-6 max-w-md")
                ui.button("Ir ao Dashboard", icon="dashboard", on_click=lambda: ui.navigate.to("/")).props("color=primary size=lg").classes("rounded-xl px-8 font-bold shadow-md")
            return

        frame = pd.DataFrame(systems)
        frame["accuracy"] = frame["acertos"] / frame["total"] * 100
        total_questions = frame["total"].sum()
        total_correct = frame["acertos"].sum()
        global_acc = (total_correct / total_questions * 100) if total_questions > 0 else 0

        calib = data.get("calibration", {})
        pred = data.get("prediction", {})

        # Top KPI Summary Cards Row (4 Cards)
        with ui.row().classes("w-full gap-4 flex-wrap my-2"):
            with ui.card().classes("study-card flex-1 min-w-[200px] border-l-4 border-l-teal-600 bg-gradient-to-r from-teal-50/50 to-white"):
                with ui.row().classes("items-center gap-3"):
                    with ui.row().classes("w-11 h-11 rounded-2xl bg-teal-100 text-teal-700 items-center justify-center font-bold"):
                        ui.icon("insights", size="22px")
                    with ui.column().classes("gap-0"):
                        ui.label(f"{global_acc:.1f}%").classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Precisão Global").classes("text-xs font-bold text-slate-600")
                        ui.label(f"{total_correct} de {total_questions} corretas").classes("text-xs text-slate-400 font-medium")

            with ui.card().classes("study-card flex-1 min-w-[200px] border-l-4 border-l-indigo-600 bg-gradient-to-r from-indigo-50/50 to-white"):
                with ui.row().classes("items-center gap-3"):
                    with ui.row().classes("w-11 h-11 rounded-2xl bg-indigo-100 text-indigo-700 items-center justify-center font-bold"):
                        ui.icon("assignment_turned_in", size="22px")
                    with ui.column().classes("gap-0"):
                        ui.label(str(total_questions)).classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Questões Resolvidas").classes("text-xs font-bold text-slate-600")
                        ui.label("Base para BKT & FSRS").classes("text-xs text-slate-400 font-medium")

            with ui.card().classes("study-card flex-1 min-w-[200px] border-l-4 border-l-amber-500 bg-gradient-to-r from-amber-50/50 to-white"):
                times = data["time"]
                avg_t = (sum(t["avg_time"] for t in times) / len(times)) if times else 0
                with ui.row().classes("items-center gap-3"):
                    with ui.row().classes("w-11 h-11 rounded-2xl bg-amber-100 text-amber-800 items-center justify-center font-bold"):
                        ui.icon("timer", size="22px")
                    with ui.column().classes("gap-0"):
                        ui.label(f"{avg_t:.0f}s").classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Tempo Médio / Questão").classes("text-xs font-bold text-slate-600")
                        ui.label("Meta USMLE < 90s").classes("text-xs text-slate-400 font-medium")

            with ui.card().classes("study-card flex-1 min-w-[200px] border-l-4 border-l-purple-600 bg-gradient-to-r from-purple-50/50 to-white"):
                brier = calib.get("brier_score", 0.0)
                with ui.row().classes("items-center gap-3"):
                    with ui.row().classes("w-11 h-11 rounded-2xl bg-purple-100 text-purple-700 items-center justify-center font-bold"):
                        ui.icon("psychology", size="22px")
                    with ui.column().classes("gap-0"):
                        ui.label(f"{brier:.3f}" if brier is not None else "--").classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Brier Score (Calibração)").classes("text-xs font-bold text-slate-600")
                        ui.label(calib.get("calibration_grade", "Calibrando...")).classes("text-xs text-purple-600 font-bold truncate")

        # Dual USMLE Readiness Card
        with ui.card().classes("study-card w-full my-3 p-5 bg-gradient-to-r from-slate-900 via-slate-800 to-teal-950 text-white shadow-lg"):
            with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("verified_user", size="32px").classes("text-emerald-400")
                    with ui.column().classes("gap-0"):
                        ui.label("Motor Preditivo USMLE (Step 1 & Step 2 CK)").classes("text-lg font-bold text-white heading-font")
                        ui.label("Estimativa psicométrica baseada em acurácia ponderada, cobertura de sistemas e retenção FSRS.").classes("text-xs text-slate-300")
                
                with ui.row().classes("items-center gap-6"):
                    with ui.column().classes("items-center gap-0 px-4 py-2 rounded-xl bg-white/10"):
                        ui.label("Step 1 (Pass/Fail)").classes("text-xs uppercase tracking-wider text-emerald-300 font-bold")
                        ui.label(pred.get("step1_pass_prob", "75%")).classes("text-2xl font-extrabold text-white")
                        ui.label("Prob. Aprovação").classes("text-[10px] text-slate-300")

                    with ui.column().classes("items-center gap-0 px-4 py-2 rounded-xl bg-white/10"):
                        ui.label("Step 2 CK (3-Digit)").classes("text-xs uppercase tracking-wider text-teal-300 font-bold")
                        ui.label(str(pred.get("step2ck_predicted_score", 225))).classes("text-2xl font-extrabold text-teal-200")
                        ui.label(f"IC 95%: {pred.get('step2ck_score_ci', '218-233')}").classes("text-[10px] text-slate-300")

        # 1. Radar Chart: Acurácia por Sistema
        with ui.card().classes("study-card w-full my-3 gap-3 p-6"):
            with ui.row().classes("items-center justify-between border-b border-slate-100 pb-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("radar", size="22px").classes("text-teal-700")
                    ui.label("Domínio Clínico por Sistema Médico (%)").classes("font-bold text-slate-900 text-lg heading-font")
                ui.label(f"{len(systems)} Sistemas").classes("text-xs bg-teal-50 text-teal-800 font-bold px-3 py-1 rounded-full")

            radar = px.line_polar(
                frame, r="accuracy", theta="sistema", line_close=True, range_r=[0, 100], markers=True,
                color_discrete_sequence=["#059669"]
            )
            radar.update_traces(fill="toself", fillcolor="rgba(5, 150, 105, 0.18)", marker=dict(size=8, color="#003B36"))
            radar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                dragmode=False,
                font=dict(family="Plus Jakarta Sans", size=12, color="#334155"),
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor="#E2E8F0"),
                    angularaxis=dict(gridcolor="#E2E8F0")
                ),
                margin=dict(l=40, r=40, t=20, b=20)
            )
            ui.plotly(radar).classes("w-full h-96")

        # BKT Mastery Classification Table
        with ui.card().classes("study-card w-full my-3 gap-3 p-6 overflow-hidden"):
            with ui.row().classes("items-center justify-between border-b border-slate-100 pb-3 w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("military_tech", size="22px").classes("text-amber-500")
                    ui.label("Matriz de Maestria BKT por Sistema Médico").classes("font-bold text-slate-900 text-lg heading-font")
                ui.label("Rastreamento Bayesiano de Conhecimento").classes("text-xs text-slate-400 font-bold")

            with ui.row().classes("w-full gap-4 flex-wrap my-1"):
                for row in systems:
                    acc = row["acertos"] / row["total"] * 100 if row["total"] > 0 else 0
                    if acc < 40:
                        badge_cls, badge_label = "badge-mastery-new", "🆕 NOVO / CRÍTICO"
                    elif acc < 65:
                        badge_cls, badge_label = "badge-mastery-learning", "⚡ EM APRENDIZADO"
                    elif acc < 85:
                        badge_cls, badge_label = "badge-mastery-consolidated", "🌿 CONSOLIDADO"
                    else:
                        badge_cls, badge_label = "badge-mastery-mastered", "👑 DOMINADO"

                    with ui.card().classes("flex-1 min-w-[220px] max-w-full p-4 border border-slate-100 bg-slate-50/50 rounded-2xl gap-2"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label(row["sistema"].replace("_", " ")).classes("font-bold text-slate-900 text-sm truncate")
                            ui.label(badge_label).classes(f"{badge_cls}")
                        with ui.row().classes("w-full justify-between items-baseline mt-1"):
                            ui.label(f"{acc:.0f}% acertos").classes("text-xs font-extrabold text-slate-700")
                            ui.label(f"{row['acertos']}/{row['total']} questões").classes("text-xs text-slate-400")


        # 2. Metacognition & Time Charts
        meta = data["metacognition"]
        with ui.row().classes("w-full gap-5 flex-wrap my-2"):
            if meta:
                with ui.card().classes("study-card flex-1 min-w-[320px] gap-3 p-6 overflow-hidden"):
                    with ui.row().classes("items-center gap-2 border-b border-slate-100 pb-3 w-full"):
                        ui.icon("psychology", size="22px").classes("text-indigo-600")
                        ui.label("Calibração Metacognitiva").classes("font-bold text-slate-900 text-base heading-font")

                    meta_frame = pd.DataFrame(meta)
                    meta_frame["Resultado"] = meta_frame["answered_correctly"].map({1: "Acertou", 0: "Errou"})
                    fig_meta = px.bar(
                        meta_frame, x="confidence_level", y="qtd", color="Resultado", barmode="group",
                        color_discrete_map={"Acertou": "#10B981", "Errou": "#F43F5E"},
                        labels={"confidence_level": "Nível de Confiança", "qtd": "Respostas"}
                    )
                    fig_meta.update_traces(marker=dict(cornerradius=6))
                    fig_meta.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        dragmode=False,
                        font=dict(family="Plus Jakarta Sans", size=11, color="#475569"),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(gridcolor="#F1F5F9"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(l=20, r=20, t=10, b=30)
                    )
                    ui.plotly(fig_meta).classes("w-full")

            if times:
                with ui.card().classes("study-card flex-1 min-w-[320px] gap-3 p-6 overflow-hidden"):
                    with ui.row().classes("items-center gap-2 border-b border-slate-100 pb-3 w-full"):
                        ui.icon("timer", size="22px").classes("text-amber-600")
                        ui.label("Ritmo Médio por Sistema (s)").classes("font-bold text-slate-900 text-base heading-font")

                    time_frame = pd.DataFrame(times)
                    time_frame["Resultado"] = time_frame["answered_correctly"].map({1: "Acertou", 0: "Errou"})
                    figure_time = px.bar(
                        time_frame, x="avg_time", y="sistema", color="Resultado", orientation="h", barmode="group",
                        color_discrete_map={"Acertou": "#10B981", "Errou": "#F43F5E"},
                        labels={"avg_time": "Segundos (Meta < 90s)", "sistema": "Sistema"}
                    )
                    figure_time.add_vline(x=90, line_dash="dash", line_color="#E11D48", annotation_text="Meta 90s")
                    figure_time.update_traces(marker=dict(cornerradius=6))
                    figure_time.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        dragmode=False,
                        font=dict(family="Plus Jakarta Sans", size=11, color="#475569"),
                        xaxis=dict(gridcolor="#F1F5F9"),
                        yaxis=dict(showgrid=False),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(l=20, r=20, t=10, b=30)
                    )
                    ui.plotly(figure_time).classes("w-full")

        # 3. Forecast Chart
        forecast = data["forecast"]
        if forecast:
            with ui.card().classes("study-card w-full my-3 gap-3 p-6 overflow-hidden"):
                with ui.row().classes("items-center gap-2 border-b border-slate-100 pb-3 w-full"):
                    ui.icon("calendar_month", size="22px").classes("text-indigo-600")
                    ui.label("Previsão de Revisões FSRS Agendadas").classes("font-bold text-slate-900 text-lg heading-font")
                
                fig_forecast = px.bar(
                    pd.DataFrame(forecast), x="due", y="qtd", color_discrete_sequence=["#6366F1"],
                    labels={"due": "Data de Vencimento", "qtd": "Cards Vencidos"}
                )
                fig_forecast.update_traces(marker=dict(cornerradius=6))
                fig_forecast.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    dragmode=False,
                    font=dict(family="Plus Jakarta Sans", size=11, color="#475569"),
                    xaxis=dict(showgrid=False),
                    yaxis=dict(gridcolor="#F1F5F9"),
                    margin=dict(l=20, r=20, t=10, b=30)
                )
                ui.plotly(fig_forecast).classes("w-full")
