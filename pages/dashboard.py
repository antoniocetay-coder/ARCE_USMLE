import logging
from datetime import datetime, timedelta, timezone

from nicegui import run, ui

from ai.client import GeminiServiceError
from config import SISTEMAS_DISPONIVEIS
from core.exceptions import QuestionGenerationError
from core.question_generation_service import QuestionGenerationService
from core.services.dashboard_service import DashboardService
from core.services.analytics_service import AnalyticsService
from pages.common import load_session, page_layout, save_session

logger = logging.getLogger(__name__)


@ui.page("/")
def dashboard_page() -> None:
    with page_layout("Dashboard", "/"):
        dashboard = DashboardService()
        due_cards, pending_questions, studied_systems = dashboard.metrics()
        streak_data = AnalyticsService().get_user_streak_data()

        # 1. Welcome Hero Banner
        with ui.card().classes("w-full p-8 rounded-3xl bg-gradient-to-r from-[#E6F8F4] via-[#F0FDF9] to-white border border-emerald-200/80 shadow-md relative overflow-hidden my-1 card-hover-lift"):
            with ui.row().classes("w-full justify-between items-center flex-wrap lg:flex-nowrap gap-6"):
                with ui.column().classes("gap-4 flex-1 min-w-80 z-10"):
                    with ui.column().classes("gap-1"):
                        ui.label("Bom dia,").classes("text-slate-500 font-semibold text-sm")
                        with ui.row().classes("items-center gap-2"):
                            ui.label("Antônio").classes("text-4xl font-extrabold text-slate-900 heading-font tracking-tight")
                            ui.label("🩺").classes("text-3xl")
                        
                        subtitle = "Sua ofensiva está mantida para hoje! 🔥" if streak_data["studied_today"] else "Faça 1 revisão ou questão hoje para manter a ofensiva!"
                        ui.label(f"Você tem {pending_questions} questões pendentes. {subtitle}").classes("text-slate-600 font-medium text-sm mt-1")

                    # Primary Action & Subtitle
                    with ui.row().classes("items-center gap-4 flex-wrap mt-2"):
                        session = load_session()
                        def start_default_session() -> None:
                            active = load_session()
                            if active.mode and active.current_item:
                                ui.navigate.to("/study")
                            else:
                                active.reset()
                                active.mode = "QBank"
                                active.queue = dashboard.create_queue("QBank")
                                save_session(active)
                                ui.navigate.to("/study")

                        btn_label = "►  Retomar sessão de hoje" if (session.mode and session.current_item) else "►  Começar sessão de hoje"
                        ui.button(btn_label, on_click=start_default_session).classes("btn-primary-dark shadow-md cursor-pointer")
                        ui.label("Continue sua jornada de aprovação.").classes("text-xs text-slate-400 font-semibold")

                # Dynamic Streak Card & 3D Illustration
                with ui.row().classes("items-center gap-6 z-10"):
                    with ui.card().classes("p-4 rounded-2xl bg-white border border-slate-100 shadow-sm gap-2 min-w-56"):
                        with ui.row().classes("items-center gap-2"):
                            with ui.row().classes("w-9 h-9 rounded-full bg-orange-100 text-orange-600 items-center justify-center border border-orange-200"):
                                ui.icon("local_fire_department", size="22px")
                            with ui.column().classes("gap-0"):
                                with ui.row().classes("items-baseline gap-1"):
                                    ui.label(str(streak_data["streak"])).classes("text-xl font-extrabold text-slate-900")
                                    ui.label("dias seguidos").classes("text-xs font-bold text-slate-600")
                                status_txt = "Estudou hoje! 🎉" if streak_data["studied_today"] else "Falta estudar hoje! 🔥"
                                ui.label(status_txt).classes("text-xs text-slate-400 font-medium")

                        # Weekday dots dynamically generated
                        with ui.row().classes("w-full justify-between items-center pt-2 border-t border-slate-100 px-1"):
                            for dot in streak_data["week_dots"]:
                                dot_cls = "day-dot-active" if dot["active"] else "day-dot-inactive"
                                ui.label(dot["label"]).classes(f"day-dot {dot_cls}").tooltip(f"{dot['date']}: {dot['count']} atividade(s)")

                    # 3D Illustration Graphic
                    ui.image("/static/stethoscope_books_3d.jpg").classes("w-40 h-36 object-contain hidden lg:block rounded-xl")

        # 2. Activity Heatmap Section (GitHub / Anki Style)
        with ui.card().classes("study-card w-full p-5 gap-3 my-2 bg-white border border-slate-200 shadow-xs"):
            with ui.row().classes("items-center justify-between border-b border-slate-100 pb-2 w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("calendar_month", size="20px").classes("text-emerald-700")
                    ui.label("Mapa de Calor da Ofensiva (Últimas 12 Semanas)").classes("font-bold text-slate-900 text-sm heading-font")
                with ui.row().classes("items-center gap-2 text-xs font-semibold text-slate-500"):
                    ui.label("Menos")
                    ui.element("div").classes("w-3 h-3 rounded-xs bg-slate-100 border border-slate-200")
                    ui.element("div").classes("w-3 h-3 rounded-xs bg-emerald-200 border border-emerald-300")
                    ui.element("div").classes("w-3 h-3 rounded-xs bg-emerald-400 border border-emerald-500")
                    ui.element("div").classes("w-3 h-3 rounded-xs bg-emerald-700 border border-emerald-800")
                    ui.label("Mais")

            # Render 12 weeks grid (84 days)
            today = datetime.now(timezone.utc).date()
            start_date = today - timedelta(days=83)
            activity_map = streak_data["activity_map"]

            with ui.row().classes("w-full flex-wrap gap-1 items-center py-2 overflow-x-auto"):
                for day_idx in range(84):
                    d = start_date + timedelta(days=day_idx)
                    d_str = d.strftime("%Y-%m-%d")
                    cnt = activity_map.get(d_str, 0)

                    if cnt == 0:
                        square_cls = "bg-slate-100 border-slate-200/80 hover:border-slate-400"
                    elif cnt <= 3:
                        square_cls = "bg-emerald-200 border-emerald-300 hover:scale-110"
                    elif cnt <= 8:
                        square_cls = "bg-emerald-400 border-emerald-500 text-white font-bold hover:scale-110"
                    else:
                        square_cls = "bg-emerald-700 border-emerald-800 text-white font-bold hover:scale-110"

                    day_formatted = d.strftime("%d/%m")
                    ui.element("div").classes(f"w-4 h-4 rounded-xs border transition-all cursor-pointer {square_cls}").tooltip(f"{day_formatted}: {cnt} atividade(s)")

        # 3. Metrics Row (3 Clean Cards)
        with ui.row().classes("w-full gap-5 flex-wrap my-3"):
            # Flashcards Vencidos
            with ui.card().classes("metric-card-clean flex-1 min-w-64 border-b-2 border-b-rose-200"):
                with ui.row().classes("items-center gap-4"):
                    with ui.row().classes("w-12 h-12 rounded-2xl bg-rose-50 text-rose-500 items-center justify-center border border-rose-100"):
                        ui.icon("event", size="24px")
                    with ui.column().classes("gap-0"):
                        ui.label(str(due_cards)).classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Flashcards vencidos").classes("text-xs font-bold text-slate-700")
                        ui.label("Excelente! Nada para revisar." if due_cards == 0 else f"{due_cards} cards aguardando.").classes("text-xs text-slate-400 mt-0.5")

            # Questões Pendentes
            with ui.card().classes("metric-card-clean flex-1 min-w-64 border-b-2 border-b-amber-200"):
                with ui.row().classes("items-center gap-4"):
                    with ui.row().classes("w-12 h-12 rounded-2xl bg-amber-50 text-amber-500 items-center justify-center border border-amber-100"):
                        ui.icon("assignment", size="24px")
                    with ui.column().classes("gap-0"):
                        ui.label(str(pending_questions)).classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Questões pendentes").classes("text-xs font-bold text-slate-700")
                        ui.label("Continue praticando hoje.").classes("text-xs text-slate-400 mt-0.5")

            # Sistemas Estudados
            with ui.card().classes("metric-card-clean flex-1 min-w-64 border-b-2 border-b-emerald-200"):
                with ui.row().classes("items-center gap-4"):
                    with ui.row().classes("w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 items-center justify-center border border-emerald-100"):
                        ui.icon("favorite", size="24px")
                    with ui.column().classes("gap-0"):
                        ui.label(str(studied_systems)).classes("text-2xl font-extrabold text-slate-900 heading-font")
                        ui.label("Sistema estudado").classes("text-xs font-bold text-slate-700")
                        ui.label("Mantenha a consistência.").classes("text-xs text-slate-400 mt-0.5")

        # Obsidian Knowledge Vault Summary Widget
        from core.repositories.knowledge_repository import KnowledgeRepository
        repo = KnowledgeRepository()
        total_ontologies = len(repo.get_ontology_counts())
        with ui.card().classes("study-card w-full p-5 gap-3 my-2 bg-gradient-to-r from-slate-900 via-slate-800 to-sky-950 text-white rounded-3xl shadow-lg border border-sky-800/40"):
            with ui.row().classes("items-center justify-between w-full flex-wrap gap-4"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("hub", size="28px").classes("text-sky-400")
                    with ui.column().classes("gap-0"):
                        ui.label("Obsidian Knowledge Vault (RAG Ativo)").classes("font-extrabold text-white text-base heading-font")
                        ui.label("Base de conhecimento médica oficial alimentando a IA em tempo real.").classes("text-xs text-sky-200/80 font-medium")

                with ui.row().classes("items-center gap-4 flex-wrap"):
                    with ui.column().classes("items-center gap-0 bg-white/10 px-4 py-2 rounded-2xl border border-white/10"):
                        ui.label("8.044").classes("text-xl font-extrabold text-sky-300")
                        ui.label("Nós Médicos").classes("text-[11px] text-slate-300 font-semibold uppercase tracking-wider")

                    with ui.column().classes("items-center gap-0 bg-white/10 px-4 py-2 rounded-2xl border border-white/10"):
                        ui.label(str(total_ontologies)).classes("text-xl font-extrabold text-teal-300")
                        ui.label("Ontologias").classes("text-[11px] text-slate-300 font-semibold uppercase tracking-wider")

                    ui.button("Explorar RAG", icon="travel_explore", on_click=lambda: ui.navigate.to("/targeted-practice")).props("color=sky").classes("rounded-xl font-bold px-4 py-2 text-xs")

        # 3. Sessão de Hoje Section
        ui.label("Sessão de hoje").classes("text-lg font-extrabold text-slate-900 heading-font mt-4 mb-2")
        with ui.row().classes("w-full gap-5 flex-wrap"):
            session_modes = [
                ("Review", "Revisão", "Revise flashcards com FSRS e consolide sua memória.", "style", "bg-emerald-100 text-emerald-800", "bg-emerald-100 text-emerald-800"),
                ("QBank", "Banco de questões", "Pratique vinhetas clínicas e teste diagnósticos.", "quiz", "bg-[#003B36] text-white", "bg-emerald-100 text-emerald-800"),
                ("Timed Exam", "Simulado Cronometrado", "Bloco NBME com timer estrito de 90s/questão.", "timer", "bg-amber-100 text-amber-800", "bg-amber-100 text-amber-800"),
                ("Drills", "Drills A vs B", "Sprints rápidos de discriminação de pares conflitantes.", "compare_arrows", "bg-blue-100 text-blue-800", "bg-blue-100 text-blue-800"),
                ("Interleaved", "Intercalado 2.0", "Misture questões, cards e drills guiados por ontologia.", "shuffle", "bg-purple-100 text-purple-800", "bg-purple-100 text-purple-800"),
                ("Caderno de Erros", "Caderno de Erros", "Refaça questões incorretas ou com dúvida.", "auto_fix_high", "bg-rose-100 text-rose-800", "bg-rose-100 text-rose-800")
            ]
            def make_launch_mode(m: str):
                def _launch() -> None:
                    active = load_session()
                    active.reset()
                    active.mode = m
                    active.queue = dashboard.create_queue(m)
                    save_session(active)
                    ui.navigate.to("/study")
                return _launch

            for mode_code, title, desc, icon, icon_style, arrow_style in session_modes:
                with ui.card().classes("flex-1 min-w-64 p-5 rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md transition-all cursor-pointer flex flex-col justify-between gap-3").on("click", make_launch_mode(mode_code)):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.row().classes("w-10 h-10 rounded-xl " + icon_style + " items-center justify-center font-bold"):
                            ui.icon(icon, size="20px")
                        
                        with ui.row().classes("w-8 h-8 rounded-full " + arrow_style + " items-center justify-center"):
                            ui.icon("chevron_right", size="18px")
                    
                    with ui.column().classes("gap-1 w-full mt-1"):
                        ui.label(title).classes("font-extrabold text-slate-900 text-base heading-font")
                        ui.label(desc).classes("text-xs text-slate-400 font-medium leading-relaxed")

        # Confusions Widget Section
        confusions = dashboard.get_confusions()
        if confusions:
            ui.label("Armadilhas & Confusões Recorrentes").classes("text-lg font-extrabold text-slate-900 heading-font mt-6 mb-2")
            with ui.card().classes("w-full p-5 rounded-2xl border border-amber-200 bg-amber-50/50 shadow-sm gap-3"):
                with ui.row().classes("items-center justify-between border-b border-amber-200 pb-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("warning", size="20px").classes("text-amber-600")
                        ui.label("Mapeamento de Lacunas de Conhecimento").classes("font-bold text-amber-950 text-sm")
                    ui.label(f"{len(confusions)} Armadilhas Detectadas").classes("text-xs font-bold bg-amber-100 text-amber-900 px-2.5 py-0.5 rounded-full")

                with ui.column().classes("w-full gap-2"):
                    for c in confusions[:3]:
                        with ui.row().classes("w-full items-center justify-between bg-white p-3 rounded-xl border border-amber-200/80 shadow-2xs"):
                            with ui.row().classes("items-center gap-2 text-xs font-bold text-slate-700 flex-wrap"):
                                ui.label("Correto:").classes("text-emerald-700")
                                ui.label(c["tag_correct"]).classes("bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded")
                                ui.icon("swap_horiz", size="16px").classes("text-amber-500")
                                ui.label("Confundido com:").classes("text-rose-700")
                                ui.label(c["tag_confused"]).classes("bg-rose-100 text-rose-800 px-2 py-0.5 rounded")
                            
                            ui.button("Treinar Foco →", on_click=lambda: ui.navigate.to("/targeted-practice")).props("flat color=amber size=sm").classes("font-bold text-xs")

        # 4. Planos Sugeridos Section
        ui.label("Planos sugeridos").classes("text-lg font-extrabold text-slate-900 heading-font mt-6 mb-2")
        with ui.row().classes("w-full gap-5 flex-wrap"):
            plans = dashboard.study_plans()

            for plan in plans:
                with ui.card().classes("flex-1 min-w-72 p-6 rounded-2xl border border-slate-200 bg-white shadow-sm flex flex-col justify-between gap-4"):
                    with ui.column().classes("w-full gap-3"):
                        with ui.row().classes("items-center justify-between w-full"):
                            with ui.row().classes("w-10 h-10 rounded-xl " + plan["icon_cls"] + " items-center justify-center font-bold"):
                                ui.icon(plan["icon"], size="20px")
                            
                            if plan["badge"]:
                                ui.label(plan["badge"]).classes("text-xs font-bold px-3 py-1 rounded-full " + plan["badge_cls"])

                        with ui.column().classes("gap-1"):
                            ui.label(plan["titulo"]).classes("font-extrabold text-slate-900 text-lg heading-font")
                            ui.label(plan["sistemas"]).classes("text-xs font-bold text-slate-500")
                            ui.label(plan["desc"]).classes("text-xs text-slate-400 font-medium mt-1 leading-relaxed")

                    # Meta row: 5 questões, ~15 min
                    with ui.column().classes("w-full gap-3 pt-3 border-t border-slate-100"):
                        with ui.row().classes("items-center gap-4 text-xs text-slate-400 font-semibold"):
                            with ui.row().classes("items-center gap-1"):
                                ui.icon("assignment", size="16px")
                                ui.label(f"{plan['quantity']} questões")
                            with ui.row().classes("items-center gap-1"):
                                ui.icon("schedule", size="16px")
                                ui.label(plan["time"] + " tempo estimado")

                        status = ui.label().classes("text-xs text-teal-700 font-semibold")
                        with ui.row().classes("w-full items-center gap-2"):
                            action = ui.button("Praticar este plano →").classes("btn-primary-dark flex-1 shadow-sm cursor-pointer")
                            bookmark_btn = ui.button(icon="bookmark_border").props("flat color=slate").classes("border border-slate-200 rounded-xl p-2")

                            async def start_plan(
                                selected_plan: dict = plan,
                                generate_button=action,
                                status_label=status,
                            ) -> None:
                                generate_button.disable()
                                quantity = int(selected_plan["quantity"])
                                status_label.set_text(f"Gerando {quantity} questões com Gemini...")
                                navigated = False
                                try:
                                    service = QuestionGenerationService()
                                    rows = await run.io_bound(
                                        service.generate_study_plan_questions,
                                        selected_plan["sistemas"].split(" • "),
                                        selected_plan["tags"],
                                        selected_plan["difficulty"],
                                        selected_plan["cognitive_order"],
                                        quantity,
                                    )
                                    s = load_session()
                                    service.populate_study_session(s, selected_plan["titulo"], rows)
                                    save_session(s)
                                    navigated = True
                                    ui.navigate.to("/study")
                                except (QuestionGenerationError, GeminiServiceError) as error:
                                    logger.exception("Question generation failed for study plan")
                                    ui.notify(str(error), type="negative")
                                except Exception:
                                    logger.exception("Unexpected study-plan generation failure")
                                    ui.notify("Não foi possível gerar as questões. Verifique as configurações da API Gemini.", type="negative")
                                finally:
                                    if not navigated:
                                        generate_button.enable()
                                        status_label.set_text("")

                            action.on_click(start_plan)
