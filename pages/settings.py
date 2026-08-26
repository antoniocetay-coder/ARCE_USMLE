from __future__ import annotations

from nicegui import ui

from ai.client import GeminiServiceError, test_connection
from ai.settings import (
    DEFAULT_FLASHCARD_MODEL,
    DEFAULT_QUESTION_MODEL,
    MODEL_DESCRIPTIONS,
    MODEL_OPTIONS,
    clear_saved_api_key,
    load_ai_settings,
    mask_api_key,
    restore_default_ai_settings,
    save_ai_settings,
)
from core.services.ai_settings_service import AISettingsService
from pages.common import page_layout

ai_settings_service = AISettingsService()


@ui.page("/settings")
def settings_page() -> None:
    with page_layout("Configurações", "/settings"):
        with ui.column().classes("w-full gap-1 mb-2"):
            ui.label("Configurações do Sistema & IA Gemini").classes("text-3xl font-extrabold text-slate-900 heading-font tracking-tight")
            ui.label("Gerencie sua chave da API Gemini, selecione modelos de linguagem e teste conexões.").classes("text-slate-500 font-medium text-sm")

        content = ui.column().classes("w-full max-w-3xl gap-4 my-2")

        def render() -> None:
            content.clear()
            settings = load_ai_settings()
            with content:
                # Key status card
                with ui.card().classes("study-card w-full gap-4"):
                    with ui.row().classes("items-center justify-between border-b border-slate-100 pb-3"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("key", size="24px").classes("text-teal-700")
                            ui.label("Credenciais Gemini API").classes("font-bold text-slate-900 text-lg heading-font")
                        
                        source = "Configuração Local (SQLite)" if ai_settings_service.has_saved_api_key() else "Variável de Ambiente (.env)" if settings.api_key else "Nenhuma Chave"
                        ui.label(source).classes("text-xs bg-slate-100 text-slate-700 font-bold px-3 py-1 rounded-full")

                    ui.label(f"Chave ativa: {mask_api_key(settings.api_key)}").classes("text-sm font-bold text-slate-800")
                    ui.label("A chave API é armazenada com segurança localmente no SQLite e nunca é compartilhada.").classes("text-xs text-slate-500")

                    key_input = ui.input("Nova Chave API Gemini", placeholder="Cole sua chave AI Studio (AIzaSy...)", password=True, password_toggle_button=True).classes("w-full")

                # Model Selection Card
                with ui.card().classes("study-card w-full gap-4"):
                    with ui.row().classes("items-center gap-3 border-b border-slate-100 pb-3"):
                        ui.icon("tune", size="24px").classes("text-teal-700")
                        ui.label("Seleção de Modelos de Linguagem").classes("font-bold text-slate-900 text-lg heading-font")

                    question_is_custom = settings.question_model not in MODEL_OPTIONS
                    question_model = ui.select(
                        options=MODEL_OPTIONS,
                        value=settings.question_model if not question_is_custom else DEFAULT_QUESTION_MODEL,
                        label="Modelo para Geração de Questões",
                    ).classes("w-full")
                    
                    question_description = ui.label(MODEL_DESCRIPTIONS[question_model.value]).classes("text-xs text-slate-500 bg-slate-50 p-2 rounded-lg border border-slate-200")
                    question_model.on_value_change(lambda event: question_description.set_text(MODEL_DESCRIPTIONS[event.value]))
                    
                    question_custom = ui.input(
                        "Modelo personalizado para questões",
                        value=settings.question_model if question_is_custom else "",
                        placeholder="Opcional: ID de modelo customizado Gemini",
                    ).classes("w-full")

                    ui.separator().classes("my-2")

                    flashcard_is_custom = settings.flashcard_model not in MODEL_OPTIONS
                    flashcard_model = ui.select(
                        options=MODEL_OPTIONS,
                        value=settings.flashcard_model if not flashcard_is_custom else DEFAULT_FLASHCARD_MODEL,
                        label="Modelo para Flashcards, Tutor, Mnemônicos, Pérolas e Desmistificador",
                    ).classes("w-full")
                    
                    flashcard_description = ui.label(MODEL_DESCRIPTIONS[flashcard_model.value]).classes("text-xs text-slate-500 bg-slate-50 p-2 rounded-lg border border-slate-200")
                    flashcard_model.on_value_change(lambda event: flashcard_description.set_text(MODEL_DESCRIPTIONS[event.value]))
                    
                    flashcard_custom = ui.input(
                        "Modelo personalizado para flashcards",
                        value=settings.flashcard_model if flashcard_is_custom else "",
                        placeholder="Opcional: ID de modelo customizado Gemini",
                    ).classes("w-full")

                # FSRS Settings Card
                with ui.card().classes("study-card w-full gap-4"):
                    with ui.row().classes("items-center gap-3 border-b border-slate-100 pb-3"):
                        ui.icon("schedule", size="24px").classes("text-teal-700")
                        ui.label("Parâmetros do Algoritmo FSRS").classes("font-bold text-slate-900 text-lg heading-font")

                    retention_val = int(round(settings.desired_retention * 100))
                    ui.label("Taxa de Retenção Alvo Desejada (Target Retention)").classes("font-bold text-slate-800 text-sm")
                    ui.label("Controla a frequência dos intervalos de revisão. Valores maiores garantem maior retenção perto da prova, mas aumentam a carga diária de cards.").classes("text-xs text-slate-500")

                    retention_select = ui.select(
                        options={
                            80: "80% — Carga leve (Intervalos mais longos)",
                            85: "85% — Carga moderada",
                            90: "90% — Padrão FSRS Recomendado (Equilibrado)",
                            95: "95% — Carga intensa (Retenção máxima pré-exame)",
                        },
                        value=retention_val if retention_val in (80, 85, 90, 95) else 90,
                        label="Retenção Alvo FSRS",
                    ).classes("w-full")

                # USMLE Pass Predictor & Readiness Index Card
                from core.services.analytics_service import AnalyticsService
                pred = AnalyticsService().get_usmle_pass_prediction()

                with ui.card().classes("study-card w-full gap-4 bg-gradient-to-br from-slate-900 via-slate-800 to-teal-950 text-white border-0 shadow-lg"):
                    with ui.row().classes("items-center justify-between border-b border-white/10 pb-3 w-full"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("analytics", size="24px").classes("text-emerald-400")
                            ui.label("📊 Previsor de Nota & Prontidão USMLE Step 1").classes("font-bold text-white text-lg heading-font")
                        
                        ui.label(pred["status_label"]).classes("text-xs font-extrabold px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-400/30")

                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-4 my-1"):
                        with ui.column().classes("gap-1"):
                            ui.label("Índice de Prontidão Calculado").classes("text-xs font-bold text-slate-300 uppercase tracking-wider")
                            with ui.row().classes("items-baseline gap-2"):
                                ui.label(f"{pred['readiness_score']}%").classes("text-4xl font-extrabold text-emerald-400 heading-font")
                                ui.label("Readiness").classes("text-xs text-slate-300 font-semibold")

                        with ui.column().classes("gap-1"):
                            ui.label("Probabilidade de Aprovação").classes("text-xs font-bold text-slate-300 uppercase tracking-wider")
                            ui.label(pred["pass_probability"]).classes("text-3xl font-extrabold text-white heading-font")

                        with ui.column().classes("gap-1"):
                            ui.label("Score Estimado (USMLE 3-Digit)").classes("text-xs font-bold text-slate-300 uppercase tracking-wider")
                            ui.label(pred["estimated_score_range"]).classes("text-3xl font-extrabold text-teal-300 heading-font")

                    ui.separator().classes("bg-white/10 my-1")
                    with ui.row().classes("w-full justify-between items-center text-xs text-slate-300 font-medium flex-wrap gap-2"):
                        ui.label(f"🎯 Precisão QBank: {pred['accuracy_pct']}% ({pred['total_answered']} questões)")
                        ui.label(f"🧠 Retenção FSRS: {pred['fsrs_retention_pct']}%")
                        ui.label(f"🌐 Cobertura de Sistemas: {pred['systems_covered']}/15")


                def selected_models() -> tuple[str, str, float]:
                    q = (question_custom.value or "").strip() or question_model.value
                    f = (flashcard_custom.value or "").strip() or flashcard_model.value
                    r = float(retention_select.value) / 100.0
                    return q, f, r

                def test() -> None:
                    candidate = (key_input.value or "").strip() or settings.api_key
                    try:
                        q, _, _ = selected_models()
                        if not candidate:
                            raise GeminiServiceError("Informe uma chave Gemini para testar a conexão.")
                        test_connection(candidate, q)
                        ui.notify("Conexão com Gemini API testada e aprovada!", type="positive")
                    except (GeminiServiceError, ValueError) as error:
                        ui.notify(str(error), type="negative")

                def save() -> None:
                    try:
                        q, f, r = selected_models()
                        updated = save_ai_settings((key_input.value or "").strip() or None, q, f, r)
                        ui.notify(f"Configurações salvas! Retenção FSRS: {int(updated.desired_retention * 100)}%.", type="positive")
                        render()
                    except ValueError as error:
                        ui.notify(str(error), type="negative")


                # Action buttons
                with ui.row().classes("w-full gap-3 flex-wrap mt-2"):
                    ui.button("Testar Conexão", icon="wifi_tethering", on_click=test).props("outline color=primary").classes("rounded-xl font-bold")
                    ui.button("Salvar Configurações", icon="save", on_click=save).props("color=primary").classes("rounded-xl font-bold shadow-md")
                    ui.button("Apagar Chave Salva", icon="delete", on_click=lambda: (clear_saved_api_key(), render())).props("outline color=negative").classes("rounded-xl font-semibold")
                    ui.button("Restaurar Padrões", icon="restart_alt", on_click=lambda: (restore_default_ai_settings(), render())).props("flat color=primary").classes("font-semibold")

        render()
