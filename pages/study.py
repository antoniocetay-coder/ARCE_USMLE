from __future__ import annotations

import json
import time

from nicegui import run, ui

from core.exceptions import StudyApplicationError
from core.flashcard_service import review_flashcard
from core.services.study_service import StudyService
from core.services.study_workflow_service import StudyWorkflowService
from pages.common import ai_is_configured, load_session, page_layout, save_session
from state.study_session import StudySession


def sanitize_session_queue(session: StudySession) -> bool:
    """Valida e remove questões da fila salvas em cache que não existem mais no banco de dados."""
    if not session.queue:
        return False

    from core.repositories.question_repository import QuestionRepository

    valid_ids = QuestionRepository().get_all_question_ids()

    new_queue = []
    modified = False
    for item in session.queue:
        if isinstance(item, dict) and item.get("type") == "question":
            q_item = item.get("item", {})
            q_id = q_item.get("id") if isinstance(q_item, dict) else None
            if q_id is not None and q_id not in valid_ids:
                modified = True
                continue
        new_queue.append(item)

    if modified:
        session.queue = new_queue
        if session.current_index >= len(new_queue):
            session.current_index = max(0, len(new_queue) - 1)
        if not new_queue:
            session.reset()
    return modified


def _render_lab_values_dialog() -> ui.dialog:
    with ui.dialog() as dialog, ui.card().classes("w-[92vw] max-w-4xl max-h-[85vh] p-6 rounded-3xl overflow-hidden bg-white shadow-2xl"):
        with ui.row().classes("w-full justify-between items-center border-b border-slate-200 pb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("biotech", size="24px").classes("text-teal-700")
                ui.label("USMLE Normal Laboratory Values Reference").classes("text-lg font-bold text-slate-900 heading-font")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense color=grey")

        with ui.tabs().classes("w-full border-b border-slate-200 text-xs font-bold") as lab_tabs:
            t_heme = ui.tab("heme", "Hematology & Coagulation")
            t_chem = ui.tab("chem", "Serum & Renal")
            t_gas = ui.tab("gas", "Blood Gas & CSF")
            t_urine = ui.tab("urine", "Endocrine & Urine")

        with ui.tab_panels(lab_tabs, value="chem").classes("w-full overflow-y-auto max-h-[60vh] p-2"):
            with ui.tab_panel("heme"):
                ui.markdown("""
| Exame | Valor de Referência (Adultos) | Unidades SI |
| :--- | :--- | :--- |
| **Hemoglobina (Hb)** | Homem: 13.5–17.5 g/dL / Mulher: 12.0–15.5 g/dL | 135–175 g/L / 120–155 g/L |
| **Hematócrito (Ht)** | Homem: 41–53% / Mulher: 36–46% | 0.41–0.53 / 0.36–0.46 |
| **Leucócitos (WBC)** | 4,500–11,000 /mm³ | 4.5–11.0 × 10⁹/L |
| **Plaquetas** | 150,000–400,000 /mm³ | 150–400 × 10⁹/L |
| **VCM (MCV)** | 80–100 fL | 80–100 fL |
| **Reticulócitos** | 0.5–1.5% | 0.005–0.015 |
| **PT / INR** | PT: 11–13.5 s / INR: 0.8–1.1 | — |
| **aPTT** | 25–35 s | — |
| **D-Dímero** | < 0.5 µg/mL / < 500 ng/mL | < 500 µg/L |
| **Ferritina** | Homem: 20–250 ng/mL / Mulher: 10–120 ng/mL | 20–250 µg/L / 10–120 µg/L |
| **TIBC** | 250–400 µg/dL | 45–72 µmol/L |
                """).classes("w-full text-xs")

            with ui.tab_panel("chem"):
                ui.markdown("""
| Eletrólito / Painel | Valor de Referência | Unidades SI |
| :--- | :--- | :--- |
| **Sódio (Na⁺)** | 135–145 mEq/L | 135–145 mmol/L |
| **Potássio (K⁺)** | 3.5–5.0 mEq/L | 3.5–5.0 mmol/L |
| **Cloreto (Cl⁻)** | 95–105 mEq/L | 95–105 mmol/L |
| **Bicarbonato (HCO₃⁻)** | 22–28 mEq/L | 22–28 mmol/L |
| **BUN (Ureia)** | 7–20 mg/dL | 2.5–7.1 mmol/L |
| **Creatinina (Cr)** | 0.6–1.2 mg/dL | 53–106 µmol/L |
| **Glicemia em Jejum** | 70–99 mg/dL | 3.9–5.5 mmol/L |
| **Cálcio Total (Ca²⁺)** | 8.5–10.5 mg/dL | 2.1–2.6 mmol/L |
| **Magnésio (Mg²⁺)** | 1.5–2.4 mg/dL | 0.62–0.99 mmol/L |
| **Fosfato Inorgânico** | 2.5–4.5 mg/dL | 0.81–1.45 mmol/L |
| **Ácido Úrico** | 3.0–7.0 mg/dL | 0.18–0.42 mmol/L |
| **AST / ALT** | AST: 8–40 U/L / ALT: 7–56 U/L | 8–40 U/L / 7–56 U/L |
| **Bilirrubina Total** | 0.1–1.2 mg/dL (Direta: 0–0.3 mg/dL) | 1.7–20.5 µmol/L |
                """).classes("w-full text-xs")

            with ui.tab_panel("gas"):
                ui.markdown("""
| Parâmetro | Gasometria Arterial | Líquor (CSF) |
| :--- | :--- | :--- |
| **pH** | 7.35–7.45 | 7.30–7.40 |
| **pCO₂** | 35–45 mmHg | 40–50 mmHg |
| **pO₂** | 80–100 mmHg | — |
| **HCO₃⁻** | 22–26 mEq/L | 20–24 mEq/L |
| **SaO₂** | > 95% | — |
| **Pressão de Abertura CSF** | — | 70–180 mm H₂O (7–18 cm H₂O) |
| **Proteínas CSF** | — | 15–45 mg/dL |
| **Glicose CSF** | — | 40–70 mg/dL (≥ 60% da glicemia sérica) |
| **Células CSF** | — | 0–5 linfócitos / µL |
                """).classes("w-full text-xs")

            with ui.tab_panel("urine"):
                ui.markdown("""
| Parâmetro | Urina & Hormônios | Valor Típico |
| :--- | :--- | :--- |
| **Osmolalidade Urinária** | 300–900 mOsm/kg | — |
| **Sódio Urinário (UNa)** | > 20 mEq/L (Normal) | < 20 mEq/L em Pré-Renal |
| **FeNa** | < 1% (Pré-Renal) | > 2% em NTA / Renal Intrínseco |
| **TSH** | 0.4–4.0 µIU/mL | — |
| **T4 Livre** | 0.8–1.8 ng/dL | 10–23 pmol/L |
| **Troponina I** | < 0.04 ng/mL | — |
| **BNP** | < 100 pg/mL | — |
                """).classes("w-full text-xs")

        with ui.row().classes("w-full justify-end mt-2"):
            ui.button("Fechar", on_click=dialog.close).props("color=primary").classes("rounded-xl font-bold text-xs px-5")
    return dialog


def _render_medical_calculator_dialog() -> ui.dialog:
    with ui.dialog() as dialog, ui.card().classes("w-[92vw] max-w-2xl max-h-[85vh] p-6 rounded-3xl overflow-hidden bg-white shadow-2xl"):
        with ui.row().classes("w-full justify-between items-center border-b border-slate-200 pb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("calculate", size="24px").classes("text-teal-700")
                ui.label("Calculadora Médica USMLE").classes("text-lg font-bold text-slate-900 heading-font")
            ui.button(icon="close", on_click=dialog.close).props("flat round dense color=grey")

        with ui.tabs().classes("w-full border-b border-slate-200 text-xs font-bold") as calc_tabs:
            t_ag = ui.tab("ag", "Anion Gap")
            t_fena = ui.tab("fena", "FeNa")
            t_winters = ui.tab("winters", "Winters' (Acidose)")
            t_osmgap = ui.tab("osmgap", "Osmolar Gap")
            t_aa = ui.tab("aa", "A-a Gradient")

        with ui.tab_panels(calc_tabs, value="ag").classes("w-full p-2 overflow-y-auto max-h-[60vh]"):
            with ui.tab_panel("ag"):
                ui.label("Anion Gap Sérico = Na⁺ - (Cl⁻ + HCO₃⁻)").classes("text-xs font-bold text-slate-500 mb-2")
                with ui.row().classes("w-full gap-3"):
                    na_in = ui.number("Na⁺ (mEq/L)", value=140).classes("flex-1")
                    cl_in = ui.number("Cl⁻ (mEq/L)", value=100).classes("flex-1")
                    hco3_in = ui.number("HCO₃⁻ (mEq/L)", value=24).classes("flex-1")
                ag_res = ui.label("Anion Gap: 16.0 mEq/L (Normal: 8–12)").classes("text-base font-extrabold text-teal-800 mt-2")
                def update_ag():
                    na = float(na_in.value or 0)
                    cl = float(cl_in.value or 0)
                    hco3 = float(hco3_in.value or 0)
                    res = na - (cl + hco3)
                    status = "Elevado (MUDPILES / GOLDMARK)" if res > 12 else "Normal (Hiperclorêmica / HARDASS)"
                    ag_res.set_text(f"Anion Gap: {res:.1f} mEq/L — {status}")
                na_in.on_value_change(update_ag)
                cl_in.on_value_change(update_ag)
                hco3_in.on_value_change(update_ag)

            with ui.tab_panel("fena"):
                ui.label("FeNa (%) = (UNa × SCr) / (SNa × UCr) × 100").classes("text-xs font-bold text-slate-500 mb-2")
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    una_in = ui.number("Na⁺ Urinário (mEq/L)", value=15).classes("flex-1 min-w-32")
                    sna_in = ui.number("Na⁺ Sérico (mEq/L)", value=140).classes("flex-1 min-w-32")
                    ucr_in = ui.number("Cr Urinária (mg/dL)", value=100).classes("flex-1 min-w-32")
                    scr_in = ui.number("Cr Sérica (mg/dL)", value=2.0).classes("flex-1 min-w-32")
                fena_res = ui.label("FeNa: 0.21% (Pré-Renal < 1%)").classes("text-base font-extrabold text-teal-800 mt-2")
                def update_fena():
                    una, sna = float(una_in.value or 0), float(sna_in.value or 1)
                    ucr, scr = float(ucr_in.value or 1), float(scr_in.value or 0)
                    if sna > 0 and ucr > 0:
                        val = (una * scr) / (sna * ucr) * 100
                        status = "Azotemia Pré-Renal (< 1%)" if val < 1.0 else "NTA / Necrose Tubular Aguda (> 2%)" if val > 2.0 else "Indeterminado (1-2%)"
                        fena_res.set_text(f"FeNa: {val:.2f}% — {status}")
                una_in.on_value_change(update_fena)
                sna_in.on_value_change(update_fena)
                ucr_in.on_value_change(update_fena)
                scr_in.on_value_change(update_fena)

            with ui.tab_panel("winters"):
                ui.label("Winters' Formula: pCO₂ Esperada = (1.5 × [HCO₃⁻]) + 8 ± 2").classes("text-xs font-bold text-slate-500 mb-2")
                with ui.row().classes("w-full gap-3"):
                    w_hco3 = ui.number("HCO₃⁻ Sérico (mEq/L)", value=12).classes("flex-1")
                    w_pco2 = ui.number("pCO₂ Medida (mmHg)", value=26).classes("flex-1")
                winters_res = ui.label("pCO₂ Esperada: 24 - 28 mmHg (Compensação Adequada)").classes("text-base font-extrabold text-teal-800 mt-2")
                def update_winters():
                    h = float(w_hco3.value or 0)
                    p = float(w_pco2.value or 0)
                    exp = (1.5 * h) + 8
                    low, high = exp - 2, exp + 2
                    status = "Compensação Respiratória Pura" if low <= p <= high else "Acidose Respiratória Concomitante" if p > high else "Alcalose Respiratória Concomitante"
                    winters_res.set_text(f"pCO₂ Esperada: {low:.1f} - {high:.1f} mmHg — {status}")
                w_hco3.on_value_change(update_winters)
                w_pco2.on_value_change(update_winters)

            with ui.tab_panel("osmgap"):
                ui.label("Osmolar Gap = Osm Medida - [2×Na⁺ + Glicose/18 + BUN/2.8]").classes("text-xs font-bold text-slate-500 mb-2")
                with ui.row().classes("w-full gap-3 flex-wrap"):
                    m_osm = ui.number("Osm Medida (mOsm/kg)", value=310).classes("flex-1 min-w-32")
                    o_na = ui.number("Na⁺ (mEq/L)", value=140).classes("flex-1 min-w-32")
                    o_glu = ui.number("Glicemia (mg/dL)", value=90).classes("flex-1 min-w-32")
                    o_bun = ui.number("BUN (mg/dL)", value=14).classes("flex-1 min-w-32")
                osmgap_res = ui.label("Osmolar Gap: 20.0 mOsm/kg (> 10)").classes("text-base font-extrabold text-teal-800 mt-2")
                def update_osmgap():
                    calc = 2 * float(o_na.value or 0) + (float(o_glu.value or 0) / 18.0) + (float(o_bun.value or 0) / 2.8)
                    gap = float(m_osm.value or 0) - calc
                    status = "Elevado (>10: Metanol, Etilenoglicol, Propilenoglicol)" if gap > 10 else "Normal (≤10)"
                    osmgap_res.set_text(f"Osmolar Gap: {gap:.1f} mOsm/kg — {status}")
                m_osm.on_value_change(update_osmgap)
                o_na.on_value_change(update_osmgap)
                o_glu.on_value_change(update_osmgap)
                o_bun.on_value_change(update_osmgap)

            with ui.tab_panel("aa"):
                ui.label("A-a Gradient = [150 - (pCO₂ / 0.8)] - PaO₂ (em ar ambiente)").classes("text-xs font-bold text-slate-500 mb-2")
                with ui.row().classes("w-full gap-3"):
                    aa_pco2 = ui.number("pCO₂ Arterial (mmHg)", value=40).classes("flex-1")
                    aa_pao2 = ui.number("PaO₂ Arterial (mmHg)", value=95).classes("flex-1")
                    aa_age = ui.number("Idade (anos)", value=25).classes("flex-1")
                aa_res = ui.label("Gradiente A-a: 5.0 mmHg (Normal: < 10)").classes("text-base font-extrabold text-teal-800 mt-2")
                def update_aa():
                    pco2 = float(aa_pco2.value or 40)
                    pao2 = float(aa_pao2.value or 95)
                    age = float(aa_age.value or 25)
                    pAo2 = 150.0 - (pco2 / 0.8)
                    grad = pAo2 - pao2
                    normal_limit = (age / 4.0) + 4.0
                    status = "Normal (Hipoventilação ou Grande Altitude)" if grad <= normal_limit else "Elevado (V/Q Mismatch, Shunt ou Defeito de Difusão)"
                    aa_res.set_text(f"Gradiente A-a: {grad:.1f} mmHg (Limite Normal: ~{normal_limit:.1f}) — {status}")
                aa_pco2.on_value_change(update_aa)
                aa_pao2.on_value_change(update_aa)
                aa_age.on_value_change(update_aa)

        with ui.row().classes("w-full justify-end mt-2"):
            ui.button("Fechar", on_click=dialog.close).props("color=primary").classes("rounded-xl font-bold text-xs px-5")
    return dialog


@ui.page("/study")
def study_page() -> None:
    with page_layout("Estudo", "/study"):
        content = ui.column().classes("w-full")
        lab_dialog = _render_lab_values_dialog()
        calc_dialog = _render_medical_calculator_dialog()
        active_callbacks: dict[str, Any] = {}

        def handle_key(e) -> None:
            if hasattr(e, "action") and getattr(e.action, "keydown", None) is False:
                return
            session = load_session()
            item = session.current_item
            if not item:
                return

            raw_key = getattr(e.key, "name", str(e.key)).lower() if e.key is not None else ""
            is_space = (getattr(e.key, "space", False) is True) or raw_key in (" ", "space")
            is_enter = raw_key in ("enter", "return")

            if item["type"] == "flashcard":
                if not session.reveal_flashcard and is_space:
                    session.reveal_flashcard = True
                    save_session(session)
                    refresh()
                elif session.reveal_flashcard:
                    if is_space or raw_key == "3":
                        card_dict = item.get("item", {})
                        interval = review_flashcard(card_dict, 3)
                        session.requeue_item(item, "Good")
                        _next(session, refresh)
                    elif raw_key in ("1", "2", "4"):
                        grade_map = {"1": 1, "2": 2, "4": 4}
                        grade_val = grade_map[raw_key]
                        grade_name = {1: "Again", 2: "Hard", 4: "Easy"}[grade_val]
                        card_dict = item.get("item", {})
                        interval = review_flashcard(card_dict, grade_val)
                        session.requeue_item(item, grade_name)
                        _next(session, refresh)

            elif item["type"] == "drill":
                if not session.answer_submitted:
                    if raw_key == "a" and "drill_a" in active_callbacks:
                        active_callbacks["drill_a"]()
                    elif raw_key == "b" and "drill_b" in active_callbacks:
                        active_callbacks["drill_b"]()
                elif session.answer_submitted and (is_space or is_enter):
                    _next(session, refresh)

            elif item["type"] == "question":
                if not session.answer_submitted:
                    key_map = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "1": 0, "2": 1, "3": 2, "4": 3, "5": 4}
                    if raw_key in key_map and "select_option" in active_callbacks:
                        active_callbacks["select_option"](key_map[raw_key])
                    elif is_enter and "submit" in active_callbacks:
                        active_callbacks["submit"]()
                elif session.answer_submitted and (is_space or is_enter):
                    _next(session, refresh)

        ui.keyboard(on_key=handle_key)

        def refresh() -> None:
            active_callbacks.clear()
            content.clear()
            session = load_session()
            if sanitize_session_queue(session):
                save_session(session)

            with content:
                if not session.mode or not session.queue:
                    with ui.card().classes("study-card w-full text-center items-center py-12 bg-white border border-slate-200 rounded-3xl shadow-sm"):
                        ui.icon("school", size="48px").classes("text-slate-300 mb-2")
                        ui.label("Nenhuma Sessão Ativa").classes("text-2xl font-bold text-slate-800 heading-font")
                        ui.label("As questões de teste foram limpas. Escolha um modo de estudo ou gere novas questões no Dashboard.").classes("text-slate-500 mb-4 text-sm")
                        ui.button("Ir ao Dashboard", icon="dashboard", on_click=lambda: ui.navigate.to("/")).props("color=primary").classes("rounded-xl px-6 font-bold shadow-md")
                    return
                
                item = session.current_item
                if item is None:
                    _render_session_summary(session, refresh)
                    return

                # Header Progress Row
                with ui.column().classes("w-full gap-2 mb-4"):
                    with ui.row().classes("w-full justify-between items-center"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("school", size="22px").classes("text-teal-700")
                            ui.label(f"Modo {session.mode}").classes("font-extrabold text-slate-800 text-lg heading-font")
                            ui.label(f"· Item {session.current_index + 1} de {len(session.queue)}").classes("text-slate-500 text-sm font-semibold")
                        
                        with ui.dialog() as end_dialog, ui.card().classes("p-6 rounded-2xl max-w-md"):
                            ui.label("Encerrar Sessão de Estudo?").classes("text-xl font-bold text-slate-900 heading-font")
                            ui.label(f"Restam {session.remaining_count()} item(ns) na fila. Itens pendentes não serão respondidos nem salvos como erro.").classes("text-slate-600 text-sm my-2")
                            with ui.row().classes("w-full justify-end gap-3 mt-4"):
                                ui.button("Continuar Estudando", on_click=end_dialog.close).props("flat").classes("font-semibold")
                                def confirm_end() -> None:
                                    session.end()
                                    save_session(session)
                                    end_dialog.close()
                                    ui.navigate.to("/")
                                ui.button("Encerrar", on_click=confirm_end).props("color=negative").classes("rounded-xl font-bold")
                        
                        ui.button("Encerrar Sessão", icon="stop", on_click=end_dialog.open).props("flat color=negative size=sm").classes("rounded-lg font-semibold")

                    progress_pct = (session.current_index) / len(session.queue) if session.queue else 0
                    ui.linear_progress(progress_pct).classes("w-full h-2 rounded-full").props("color=teal track-color=slate-200 show-value=false")

                if item["type"] == "question":
                    _render_question(item, session, refresh, active_callbacks, lab_dialog, calc_dialog)
                elif item["type"] == "drill":
                    _render_drill(item, session, refresh, active_callbacks)
                else:
                    _render_flashcard(item, session, refresh)
                    
        refresh()


def _next(session, refresh) -> None:
    session.next_item()
    save_session(session)
    refresh()


def _render_session_summary(session, refresh) -> None:
    questions = [r for r in session.session_results if isinstance(r, dict) and r.get("item_type") == "question"]
    total = len(questions)
    correct = sum(1 for q in questions if q.get("is_correct"))
    acc = (correct / total * 100) if total > 0 else 0
    avg_time = sum(q.get("time_taken", 0) for q in questions) / total if total > 0 else 0
    flashcard_count = sum(1 for item in session.queue if isinstance(item, dict) and item.get("type") == "flashcard")

    with ui.column().classes("w-full items-center"):
        with ui.card().classes("study-card w-full text-center items-center p-8 bg-gradient-to-b from-teal-50 to-white border-teal-200 mb-6"):
            ui.image("/static/medical_trophy_3d.jpg").classes("w-28 h-28 object-contain mb-3 rounded-2xl shadow-md")
            ui.label("Sessão Concluída!").classes("text-3xl font-extrabold text-teal-900 heading-font tracking-tight mb-1")
            ui.label("Seu boletim de desempenho nesta sessão.").classes("text-slate-500 font-semibold text-sm")

        with ui.row().classes("w-full gap-6 justify-center mb-6 flex-wrap"):
            if total > 0:
                # Accuracy Card
                with ui.card().classes("study-card flex-1 min-w-[200px] text-center p-6 bg-emerald-50 border-emerald-200"):
                    ui.label("PRECISÃO").classes("text-xs font-extrabold text-emerald-800 tracking-widest mb-1")
                    ui.label(f"{acc:.0f}%").classes("text-4xl font-extrabold text-emerald-950 heading-font")
                    ui.label(f"{correct} de {total} corretas").classes("text-emerald-700 text-xs font-bold mt-1")

                # Time Card
                with ui.card().classes("study-card flex-1 min-w-[200px] text-center p-6 bg-amber-50 border-amber-200"):
                    ui.label("RITMO").classes("text-xs font-extrabold text-amber-800 tracking-widest mb-1")
                    ui.label(f"{avg_time:.0f}s").classes("text-4xl font-extrabold text-amber-950 heading-font")
                    ui.label("por questão").classes("text-amber-700 text-xs font-bold mt-1")

                if flashcard_count > 0:
                    with ui.card().classes("study-card flex-1 min-w-[200px] text-center p-6 bg-teal-50 border-teal-200"):
                        ui.label("FLASHCARDS").classes("text-xs font-extrabold text-teal-800 tracking-widest mb-1")
                        ui.label(f"{flashcard_count}").classes("text-4xl font-extrabold text-teal-950 heading-font")
                        ui.label("cards revisados").classes("text-teal-700 text-xs font-bold mt-1")
            else:
                with ui.card().classes("study-card flex-1 min-w-[200px] text-center p-6 bg-teal-50 border-teal-200"):
                    ui.label("FLASHCARDS").classes("text-xs font-extrabold text-teal-800 tracking-widest mb-1")
                    ui.label(f"{len(session.queue)}").classes("text-4xl font-extrabold text-teal-950 heading-font")
                    ui.label("cards revisados").classes("text-teal-700 text-xs font-bold mt-1")

        # Metacognition Quick Breakdown
        with ui.card().classes("study-card w-full p-6 bg-white mb-6"):
            ui.label("Raio-X Metacognitivo").classes("text-lg font-bold text-slate-900 mb-3 heading-font border-b border-slate-100 pb-2")

            conf_stats = {"Certeza Absoluta": [0, 0], "Dúvida entre 2": [0, 0], "Chute Cego": [0, 0]}
            for q in questions:
                conf = q.get("confidence")
                if conf in conf_stats:
                    conf_stats[conf][0] += 1
                    if q.get("is_correct"):
                        conf_stats[conf][1] += 1

            for level, (tot, corr) in conf_stats.items():
                if tot > 0:
                    with ui.row().classes("w-full items-center justify-between py-2 border-b border-slate-100"):
                        ui.label(level).classes("font-semibold text-slate-700 text-sm")
                        acc_lvl = corr / tot * 100
                        color = "text-emerald-600" if acc_lvl > 70 else "text-rose-600" if acc_lvl < 40 else "text-amber-600"
                        ui.label(f"{acc_lvl:.0f}% ({corr}/{tot})").classes(f"font-bold {color} text-sm")

        def finish() -> None:
            session.reset()
            save_session(session)
            ui.navigate.to("/")

        ui.button("Voltar ao Dashboard", icon="arrow_forward", on_click=finish).props("color=primary size=lg").classes("w-full rounded-xl font-bold py-3 shadow-md")


def _render_question(item: dict, session, refresh, active_callbacks: dict[str, Any] | None = None, lab_dialog=None, calc_dialog=None) -> None:
    row = item.get("item", {}) if isinstance(item, dict) else {}
    if "question_json" in row:
        raw = row["question_json"]
        question = json.loads(raw) if isinstance(raw, str) else raw
    else:
        question = row
    if not isinstance(question, dict):
        question = {}
    session.begin_question_timer()
    save_session(session)

    sistema = str(row.get("sistema") or question.get("sistema") or "General_Principles")
    dificuldade = str(row.get("dificuldade") or question.get("difficulty") or "Medium")

    with ui.card().classes("study-card w-full gap-6"):
        # Header Badge Row
        with ui.row().classes("w-full justify-between items-center border-b border-slate-100 pb-3 flex-wrap gap-2"):
            with ui.row().classes("items-center gap-2"):
                ui.label(sistema.replace("_", " ")).classes("bg-teal-100 text-teal-800 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider")
                ui.label(f"Dificuldade: {dificuldade}").classes("bg-slate-100 text-slate-700 text-xs font-bold px-3 py-1 rounded-full")
                if lab_dialog:
                    ui.button("Lab Values", icon="biotech", on_click=lab_dialog.open).props("flat dense color=primary size=sm").classes("rounded-lg text-xs font-bold")
                if calc_dialog:
                    ui.button("Calculadora", icon="calculate", on_click=calc_dialog.open).props("flat dense color=teal size=sm").classes("rounded-lg text-xs font-bold")

            elapsed = int(time.time() - (session.time_started or time.time()))
            timer_style = "bg-teal-50 text-teal-800 border border-teal-200" if elapsed <= 60 else "bg-amber-50 text-amber-900 border border-amber-300 font-bold" if elapsed <= 90 else "bg-slate-100 text-slate-700 border border-slate-300 font-bold"
            timer_label = f"{elapsed}s · Ritmo USMLE (<90s)" if elapsed <= 90 else f"{elapsed}s · Ritmo >90s"

            with ui.row().classes(f"items-center gap-1.5 text-xs px-3 py-1 rounded-full {timer_style}"):
                ui.icon("schedule", size="16px")
                ui.label(timer_label)

        # Vignette text with Ergonomic Container
        with ui.column().classes("vignette-container w-full"):
            ui.markdown(question.get("vignette", "")).classes("text-slate-800 text-base leading-relaxed font-medium my-1")

        ui.separator().classes("my-1")

        # Options selector
        options = question.get("options") if isinstance(question.get("options"), list) else []
        correct_answer = str(question.get("correct", "A")).strip().upper()[:1]

        current_val = session.selected_answer if session.answer_submitted else None
        if current_val and current_val not in options:
            match = next((opt for opt in options if isinstance(opt, str) and opt.startswith(current_val)), None)
            if match:
                current_val = match

        if not session.answer_submitted:
            ui.label("Selecione a Alternativa Correta (ou use teclado A-E / 1-5):").classes("font-bold text-slate-900 text-sm")
        
        answer = ui.radio(options, value=current_val).classes("w-full gap-2")

        # Distractor strike-through toolbar
        if not session.answer_submitted and options:
            with ui.row().classes("w-full items-center gap-2 mt-1 flex-wrap"):
                ui.label("Eliminar Alternativas:").classes("text-[11px] font-bold text-slate-400 uppercase tracking-wider")
                for opt_idx, opt_text in enumerate(options):
                    letter = str(opt_text)[0].upper() if opt_text else f"#{opt_idx+1}"
                    def make_strike_opt(letter_key):
                        def _strike():
                            ui.notify(f"Alternativa ({letter_key}) eliminada mentalmente.", type="info")
                        return _strike
                    ui.button(f"✂️ {letter}", on_click=make_strike_opt(letter)).props("flat dense size=xs color=grey").classes("strike-toggle-btn text-[11px] font-bold")

        # Confidence selection
        ui.label("Nível de Confiança Metacognitiva:").classes("font-bold text-slate-900 text-xs text-slate-500 uppercase tracking-wider mt-2")
        confidence = ui.radio(["Certeza Absoluta", "Dúvida entre 2", "Chute Cego"], value=session.confidence if session.answer_submitted else "Certeza Absoluta").props("inline")

        def submit() -> None:
            if not answer.value or not confidence.value:
                ui.notify("Selecione uma alternativa e seu nível de confiança.", type="warning")
                return
            result = StudyService().submit_answer(session, answer.value, confidence.value, session.time_started or time.time(), time.time())
            if not result.is_correct and confidence.value != "Chute Cego":
                tags = question.get("distractor_tags", {})
                if isinstance(tags, dict):
                    right = tags.get(question.get("correct", ""))
                    chosen = tags.get(str(answer.value)[0].upper())
                    if right and chosen:
                        StudyWorkflowService().record_confusion(right, chosen)
                
                # Schedule Isomorphic Transfer Vignette [P4] in background
                if ai_is_configured():
                    async def schedule_isomorphic():
                        try:
                            from core.ai.isomorphic_generator import agendar_vinheta_isomorfica
                            import random
                            q_id = row.get("id") or random.randint(100, 9999)
                            await run.io_bound(agendar_vinheta_isomorfica, int(q_id), question, sistema)
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).warning("Falha ao agendar vinheta isomórfica: %s", e)
                    ui.timer(0.2, schedule_isomorphic, once=True)

            # Auto-demystify if incorrect
            if not result.is_correct and not getattr(session, "demystified_response", None) and ai_is_configured():
                async def auto_demystify():
                    try:
                        res = await run.io_bound(StudyWorkflowService().demystify_distractors, question)
                        current_session = load_session()
                        if current_session.answer_submitted and not current_session.demystified_response:
                            current_session.demystified_response = res
                            save_session(current_session)
                    except Exception as error:
                        import logging
                        logging.getLogger(__name__).warning("Falha no auto-demystify: %s", error)
                ui.timer(0.1, auto_demystify, once=True)

            save_session(session)
            refresh()

        if active_callbacks is not None and not session.answer_submitted:
            active_callbacks["submit"] = submit
            def do_select(idx: int):
                if 0 <= idx < len(options):
                    answer.set_value(options[idx])
            active_callbacks["select_option"] = do_select

        if not session.answer_submitted:
            ui.button("Submeter Resposta [Enter]", icon="check_circle", on_click=submit).props("color=primary size=lg").classes("w-full rounded-xl font-bold mt-4 shadow-md")
        else:
            is_right = session.is_correct
            banner_bg = "bg-emerald-50 border-emerald-200 text-emerald-900" if is_right else "bg-rose-50 border-rose-200 text-rose-900"
            banner_icon = "check_circle" if is_right else "cancel"
            banner_title = "Resposta Correta!" if is_right else f"Resposta Incorreta — Alternativa Correta: {correct_answer}"

            with ui.row().classes(f"w-full p-4 rounded-xl border {banner_bg} items-center gap-3 my-2 shadow-sm fade-in"):
                ui.icon(banner_icon, size="28px").classes("text-emerald-600" if is_right else "text-rose-600")
                with ui.column().classes("gap-0 flex-1"):
                    ui.label(banner_title).classes("font-bold text-base")
                    ui.label(f"Tempo de resposta: {session.time_taken}s · Confiança informada: {session.confidence}").classes("text-xs opacity-80")

            # Progressive Disclosure Cockpit (Tabs with State Memory)
            current_study_tab = getattr(session, "active_study_tab", "expl") or "expl"
            with ui.tabs(value=current_study_tab).classes("w-full mt-4 border-b border-slate-200") as study_tabs:
                tab_exp = ui.tab("expl", "🎯 Explicações", icon="quiz")
                tab_dem = ui.tab("demyst", "🔍 Desmistificador", icon="psychology")
                tab_rag = ui.tab("rag", "📚 Obsidian RAG", icon="hub")
                tab_mnem = ui.tab("mnem", "🧠 Mnemônicos & Pérolas", icon="lightbulb")
                tab_card = ui.tab("card", "🪄 Flashcards", icon="style")

            def on_tab_change(e):
                val = getattr(e, "value", None) or str(e)
                session.active_study_tab = val
                save_session(session)

            study_tabs.on_value_change(on_tab_change)

            with ui.tab_panels(study_tabs, value=current_study_tab).classes("w-full bg-transparent p-0"):
                with ui.tab_panel("expl"):
                    ui.label("Explicações Detalhadas").classes("font-bold text-slate-900 text-base heading-font mt-2 slide-up")
                    for option in options:
                        is_correct_option = str(option).startswith(correct_answer)
                        card_style = "bg-emerald-50/80 border-emerald-300 text-emerald-950" if is_correct_option else "bg-slate-50 border-slate-200 text-slate-800"
                        with ui.card().classes(f"w-full p-4 border rounded-xl gap-1 {card_style} slide-up my-1"):
                            with ui.row().classes("items-center justify-between"):
                                ui.label(str(option)).classes("font-bold text-sm")
                                if is_correct_option:
                                    ui.label("CORRETA").classes("bg-emerald-600 text-white text-xs font-extrabold px-2 py-0.5 rounded")

                            opt_letter = str(option)[0] if option else ""
                            explanations = question.get("explanations", {}) if isinstance(question.get("explanations"), dict) else {}
                            explanation_text = explanations.get(opt_letter, "")
                            if explanation_text:
                                ui.label(str(explanation_text)).classes("text-xs text-slate-600 mt-1 leading-normal")

                    if question.get('educational_objective'):
                        with ui.card().classes("w-full p-4 bg-indigo-50 border border-indigo-200 rounded-xl my-2"):
                            ui.label("🎯 Objetivo Educacional USMLE").classes("font-bold text-indigo-950 text-xs uppercase tracking-wider")
                            ui.markdown(str(question.get('educational_objective', ''))).classes("text-indigo-900 text-sm mt-1")

                with ui.tab_panel("demyst"):
                    _render_demystifier_forge(question, session, refresh)

                with ui.tab_panel("rag"):
                    from components.knowledge_card import render_knowledge_node_card
                    from core.repositories.knowledge_repository import KnowledgeRepository
                    tags = question.get("content_tags", []) if isinstance(question.get("content_tags"), list) else []
                    if tags:
                        nodes = KnowledgeRepository().search_nodes(tags[0], limit=1)
                        if not nodes:
                            nodes = KnowledgeRepository().list_nodes_by_ontology(tags[0], limit=1)
                        if nodes:
                            full_node = KnowledgeRepository().get_node_by_id(nodes[0].node_id)
                            if full_node:
                                with ui.column().classes("w-full my-1 gap-1"):
                                    ui.label("📚 Fundamentação Oficial no Obsidian Vault").classes("text-xs font-extrabold text-sky-950 uppercase tracking-wider")
                                    render_knowledge_node_card(full_node)
                            else:
                                ui.label("Nenhum fragmento associado encontrado no Obsidian Vault.").classes("text-xs text-slate-500")
                        else:
                            ui.label("Nenhum fragmento associado encontrado no Obsidian Vault.").classes("text-xs text-slate-500")
                    else:
                        ui.label("Nenhum fragmento associado encontrado no Obsidian Vault.").classes("text-xs text-slate-500")

                with ui.tab_panel("mnem"):
                    _render_pearl_forge(f"Vignette: {question.get('vignette', '')}\nObjective: {question.get('educational_objective', '')}", sistema, session, refresh)
                    _render_mnemonic_forge(f"Vignette: {question.get('vignette', '')}\nObjective: {question.get('educational_objective', '')}", session, refresh, sistema=sistema)

                with ui.tab_panel("card"):
                    _render_flashcard_forge(question, sistema, session, refresh)

            ui.button("Próxima Questão [Espaço]", icon="arrow_forward", on_click=lambda: _next(session, refresh)).props("color=primary size=lg").classes("w-full rounded-xl font-bold shadow-lg my-4")


def _render_draft_flashcards_block(session, refresh, default_system: str = "General_Principles", default_tags: list[str] | None = None) -> None:
    if not session.draft_flashcards:
        return
    ui.separator().classes("my-3")
    with ui.card().classes("w-full p-5 bg-gradient-to-r from-purple-100 via-indigo-50 to-purple-50 border-2 border-purple-400 rounded-2xl shadow-md gap-3 my-2"):
        with ui.row().classes("items-center justify-between w-full border-b border-purple-200 pb-2"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("style", size="24px").classes("text-purple-800")
                ui.label(f"✨ Flashcards Gerados pela IA ({len(session.draft_flashcards)} card(s))").classes("font-extrabold text-purple-950 text-base heading-font")
            ui.label("Cards atômicos e autocontidos. Revise e clique em 'Aprovar' para adicionar à sua fila.").classes("text-xs text-purple-800 font-semibold")

        edited: list[tuple] = []
        for index, card in enumerate(session.draft_flashcards):
            with ui.card().classes("w-full p-4 bg-white border border-purple-300 rounded-xl gap-3 my-2 shadow-xs"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label(f"🃏 Flashcard #{index + 1}").classes("font-extrabold text-purple-900 text-xs uppercase tracking-wider")
                    def make_discard(idx: int):
                        def _do_discard() -> None:
                            if 0 <= idx < len(session.draft_flashcards):
                                session.draft_flashcards.pop(idx)
                                session.active_study_tab = "card"
                                save_session(session)
                                refresh()
                        return _do_discard
                    ui.button("Descartar", icon="delete", on_click=make_discard(index)).props("flat color=negative size=sm").classes("text-xs font-bold")

                from core.ai.flashcard_generator import strip_markdown
                clean_f = strip_markdown(card.get("front", ""))
                clean_b = strip_markdown(card.get("back", ""))
                front = ui.textarea("Frente (Pergunta Autocontida / Cenário Clínico)", value=clean_f).classes("w-full bg-slate-50 rounded-lg")
                back = ui.textarea("Verso (Resposta Direta + Mecanismo / Racional)", value=clean_b).classes("w-full bg-slate-50 rounded-lg")
                card_tags = card.get("tags") or default_tags or []
                edited.append((front, back, card_tags))

        def approve() -> None:
            from core.ai.flashcard_generator import strip_markdown
            saved_count = StudyWorkflowService().save_flashcards_to_session(
                session,
                [(strip_markdown(front.value), strip_markdown(back.value), tags) for front, back, tags in edited],
                default_system,
            )
            session.draft_flashcards = []
            session.flashcards_saved = True
            session.active_study_tab = "card"
            save_session(session)
            ui.notify(f"🎉 {saved_count} flashcard(s) salvo(s) e adicionado(s) à sua sessão!", type="positive")
            refresh()

        ui.button("Aprovar & Adicionar à Sessão", icon="done_all", on_click=approve).props("color=purple size=lg").classes("w-full rounded-xl font-extrabold shadow-md py-3 text-base my-2")


def _render_flashcard_forge(question: dict, sistema: str, session, refresh) -> None:
    with ui.row().classes("items-center gap-2 mt-2"):
        ui.icon("psychology", size="22px").classes("text-purple-700")
        ui.label("Reflexão Metacognitiva: Por que você errou/vacilou nesta questão?").classes("text-lg font-extrabold text-slate-900 heading-font")

    if not ai_is_configured():
        ui.label("Recursos de IA desativados: configure a chave Gemini em Configurações.").classes("text-slate-500 text-sm")
        return

    workflow = StudyWorkflowService()
    existing = workflow.existing_flashcards(question.get("content_tags", []))

    with ui.card().classes("w-full p-5 bg-gradient-to-r from-purple-50 via-indigo-50/50 to-white border border-purple-200/80 rounded-2xl shadow-xs gap-3 my-2"):
        ui.label("Explique em poucas palavras o motivo do seu erro ou dúvida. A IA gerará cards atômicos, autocontidos e estruturados para sanar cada faceta dessa lacuna!").classes("text-xs text-slate-600 font-medium leading-relaxed")

        reflection_input = ui.textarea(placeholder="Ex.: Confundi insuficiência pré-renal com NTA por causa do FeNa < 1%...").classes("w-full bg-white rounded-xl border-purple-200")

        with ui.column().classes("w-full gap-2 mt-1"):
            with ui.row().classes("gap-2 flex-wrap"):
                ui.chip("💡 Confundi dois conceitos parecidos", on_click=lambda: reflection_input.set_value("Confundi dois conceitos muito parecidos")).props("outline color=purple size=sm cursor-pointer")
                ui.chip("🧠 Faltou memorizar conduta/droga de 1ª linha", on_click=lambda: reflection_input.set_value("Faltou memorizar a conduta / tratamento de 1ª linha")).props("outline color=purple size=sm cursor-pointer")
                ui.chip("🔍 Errei a interpretação do caso clínico", on_click=lambda: reflection_input.set_value("Errei a interpretação dos dados do caso clínico")).props("outline color=purple size=sm cursor-pointer")
                ui.chip("⚡ Chutei por dúvida no mecanismo de ação", on_click=lambda: reflection_input.set_value("Chutei por dúvida no mecanismo de ação")).props("outline color=purple size=sm cursor-pointer")

        with ui.row().classes("w-full items-center justify-between gap-4 mt-2 flex-wrap"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("tune", size="18px").classes("text-purple-700")
                ui.label("Meta de Cards:").classes("text-xs font-bold text-slate-700")
                qty_select = ui.select(
                    {
                        0: "✨ Decomposição Completa & Ilimitada (IA gera todos necessários)",
                        3: "⚡ 3 Cards (Foco Rápido)",
                        6: "🎯 6 Cards (Decomposição Profunda)",
                        10: "🔬 10 Cards (Extensivo)",
                        15: "🧬 15+ Cards (Decomposição Exaustiva)"
                    },
                    value=0
                ).classes("w-80 bg-white rounded-xl text-xs").props("dense outlined")

        status_container = ui.column().classes("w-full items-center justify-center")

        async def generate(kind: str, request_text: str = "") -> None:
            btn_meta.props("loading")
            btn_meta.disable()
            btn_auto.props("loading")
            btn_auto.disable()
            btn_more.props("loading")
            btn_more.disable()
            status_container.clear()
            with status_container:
                with ui.card().classes("w-full p-4 bg-purple-100/90 border-2 border-purple-400 rounded-2xl items-center justify-center gap-2 my-2 shadow-sm"):
                    with ui.row().classes("items-center gap-3"):
                        ui.spinner("dots", size="lg", color="purple")
                        ui.label("⚡ Diagnosticando erro e gerando Flashcards Atômicos...").classes("text-base text-purple-950 font-extrabold animate-pulse")
                    ui.label("Isolando a lacuna cognitiva e construindo cards de alta retenção...").classes("text-xs text-purple-800 font-semibold")
            
            target_count = qty_select.value if qty_select.value and qty_select.value > 0 else None
            cards = []
            try:
                cards = await run.io_bound(workflow.generate_flashcards, kind, question, session, existing, request_text, target_count)
            except (StudyApplicationError, Exception) as error:
                ui.notify(str(error), type="negative")
            
            if not cards:
                try:
                    btn_meta.props(remove="loading")
                    btn_meta.enable()
                    btn_auto.props(remove="loading")
                    btn_auto.enable()
                    btn_more.props(remove="loading")
                    btn_more.enable()
                    status_container.clear()
                except Exception:
                    pass
                ui.notify("A IA não retornou nenhum flashcard válido. Tente reformular a reflexão.", type="warning")
                return

            session.draft_flashcards.extend(cards)
            session.active_study_tab = "card"
            save_session(session)
            ui.notify(f"✨ {len(cards)} flashcard(s) atômico(s) gerado(s)! Revise e aprove abaixo.", type="positive")
            refresh()

        async def submit_reflection() -> None:
            val = reflection_input.value.strip()
            if not val:
                ui.notify("Descreva em poucas palavras o motivo da sua dúvida.", type="warning")
                return
            await generate("metacognitive", val)

        btn_meta = ui.button("Gerar Flashcards Focalizados no Erro 🪄", icon="auto_awesome", on_click=submit_reflection).props("color=purple size=md").classes("w-full rounded-xl font-bold shadow-sm mt-2")

        with ui.row().classes("w-full justify-between items-center my-2"):
            ui.label("Outras Opções de Geração:").classes("text-xs font-bold text-slate-500 uppercase tracking-wider")
            with ui.row().classes("gap-2"):
                async def gen_auto():
                    await generate("error")
                async def gen_more():
                    await generate("more")
                btn_auto = ui.button("Análise Automática do Erro", icon="psychology", on_click=gen_auto).props("flat color=purple size=sm").classes("rounded-lg font-semibold text-xs")
                btn_more = ui.button("Explorar Outros Ângulos", icon="explore", on_click=gen_more).props("flat color=purple size=sm").classes("rounded-lg font-semibold text-xs")

    # Render drafts directly inside the tab
    _render_draft_flashcards_block(session, refresh, sistema, question.get("content_tags", []))

def _render_drill(item: dict, session, refresh, active_callbacks: dict[str, Any] | None = None) -> None:
    drill = item.get("item", {}) if isinstance(item, dict) else {}
    sistema = str(drill.get("sistema") or "General_Principles").replace("_", " ")
    clue = str(drill.get("prompt_clue", ""))
    concept_a = str(drill.get("concept_a", "Opção A"))
    concept_b = str(drill.get("concept_b", "Opção B"))
    correct_choice = str(drill.get("correct_choice", "A")).upper()
    pivot_exp = str(drill.get("pivot_explanation", ""))

    with ui.card().classes("drill-card w-full gap-5 p-6 border-2 border-blue-200"):
        # Header Badge
        with ui.row().classes("w-full justify-between items-center border-b border-slate-100 pb-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("compare_arrows", size="22px").classes("text-blue-600")
                ui.label(f"DRILL DE DISCRIMINAÇÃO A vs B · {sistema}").classes("text-xs font-extrabold text-blue-900 bg-blue-100 px-3 py-1 rounded-full uppercase tracking-wider")
            ui.label("⚡ Reconhecimento Rápido de Padrões (<30s)").classes("text-xs font-bold text-slate-500")

        # Pivot Clue Container
        with ui.column().classes("w-full gap-2 my-2 p-5 bg-gradient-to-r from-blue-50/70 to-indigo-50/50 rounded-2xl border border-blue-200"):
            ui.label("🔍 ACHADO CLÍNICO / PIVOT DISCRIMINATOR:").classes("text-xs font-extrabold text-blue-900 tracking-widest")
            ui.label(clue).classes("text-slate-900 text-lg font-extrabold heading-font leading-snug")

        if not session.answer_submitted:
            ui.label("Selecione a condição que corresponde a este achado (Atalhos: A / B):").classes("font-bold text-slate-700 text-xs uppercase tracking-wider mt-2")
            
            def make_submit_drill(choice: str):
                def _do_submit() -> None:
                    session.answer_submitted = True
                    session.selected_answer = choice
                    session.is_correct = (choice == correct_choice)
                    save_session(session)
                    refresh()
                return _do_submit

            if active_callbacks is not None:
                active_callbacks["drill_a"] = make_submit_drill("A")
                active_callbacks["drill_b"] = make_submit_drill("B")

            with ui.row().classes("w-full gap-4 my-2"):
                ui.button(f"A) {concept_a}", on_click=make_submit_drill("A")).classes("flex-1 drill-choice-btn drill-choice-a shadow-sm")
                ui.button(f"B) {concept_b}", on_click=make_submit_drill("B")).classes("flex-1 drill-choice-btn drill-choice-b shadow-sm")
        else:
            is_right = session.is_correct
            banner_bg = "bg-emerald-50 border-emerald-200 text-emerald-900" if is_right else "bg-rose-50 border-rose-200 text-rose-900"
            banner_icon = "check_circle" if is_right else "cancel"
            banner_title = "Correto! Padrão Reconhecido com Sucesso!" if is_right else f"Incorreto! A resposta certa era ({correct_choice})"

            with ui.row().classes(f"w-full p-4 rounded-xl border {banner_bg} items-center gap-3 my-2 shadow-sm fade-in"):
                ui.icon(banner_icon, size="28px").classes("text-emerald-600" if is_right else "text-rose-600")
                ui.label(banner_title).classes("font-bold text-base")

            # Pivot explanation box
            with ui.card().classes("w-full p-5 bg-blue-50 border border-blue-200 rounded-xl gap-2 my-2"):
                ui.label("💡 POR QUE ESSE É O DISCRIMINADOR CHAVE:").classes("text-xs font-extrabold text-blue-900 uppercase tracking-wider")
                ui.label(pivot_exp).classes("text-blue-950 text-sm font-semibold leading-relaxed")

            ui.button("Próximo Desafio [Espaço]", icon="arrow_forward", on_click=lambda: _next(session, refresh)).props("color=primary size=lg").classes("w-full rounded-xl font-bold shadow-md my-4 py-3")


def _render_flashcard(item: dict, session, refresh) -> None:
    from ai.settings import load_ai_settings
    from core.ai.flashcard_generator import strip_markdown
    from core.algorithms.fsrs import CardState, calculate_card_preview
    from core.repositories.flashcard_repository import FlashcardRepository

    card = item.get("item", {}) if isinstance(item, dict) else {}
    front_clean = strip_markdown(card.get("front", ""))
    back_clean = strip_markdown(card.get("back", ""))
    raw_system = str(card.get("sistema") or "General_Principles")
    card_system = raw_system.replace("_", " ")

    # Pre-calculate FSRS v5 telemetry and 4-grade previews
    fsrs_preview = calculate_card_preview(card, desired_retention=load_ai_settings().desired_retention)
    telem = fsrs_preview.telemetry
    r_pct = int(round(telem.current_retrievability * 100))
    r_badge_cls = "bg-emerald-100 text-emerald-900 border-emerald-300" if r_pct >= 90 else "bg-amber-100 text-amber-900 border-amber-300" if r_pct >= 80 else "bg-rose-100 text-rose-900 border-rose-300"
    state_labels = {CardState.NEW: "Novo", CardState.LEARNING: "Aprendizado", CardState.REVIEW: "Revisão", CardState.RELEARNING: "Reaprendizado"}
    state_label = state_labels.get(telem.state, "Revisão")

    with ui.card().classes("study-card w-full gap-5 border-teal-200 shadow-md bg-gradient-to-b from-white to-teal-50/20"):
        # Header Badge & Cognitive Telemetry
        with ui.column().classes("w-full gap-2 border-b border-slate-100 pb-3"):
            with ui.row().classes("w-full justify-between items-center"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("style", size="20px").classes("text-teal-600")
                    ui.label(f"FLASHCARD · {card_system}").classes("text-xs font-extrabold text-teal-800 bg-teal-100/80 px-3 py-1 rounded-full uppercase tracking-wider")

                def delete_card() -> None:
                    card_id = card.get("id")
                    if card_id:
                        FlashcardRepository().delete_flashcard(card_id)
                    if 0 <= session.current_index < len(session.queue):
                        session.queue.pop(session.current_index)
                    session.reveal_flashcard = False
                    session.tutor_response = None
                    session.mnemonic_response = None
                    session.pearl_response = None
                    session.demystified_response = None
                    session.draft_flashcards = []
                    save_session(session)
                    ui.notify("Flashcard excluído com sucesso!", type="warning")
                    refresh()

                ui.button("Excluir", icon="delete", on_click=delete_card).props("flat color=negative size=sm").classes("rounded-lg text-xs font-bold")

            # Cognitive Telemetry Bar
            with ui.row().classes("w-full justify-between items-center bg-slate-50/80 p-2.5 rounded-xl border border-slate-200 text-xs font-semibold flex-wrap gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("psychology", size="18px").classes("text-teal-700")
                    ui.label("Telemetria FSRS:").classes("text-slate-500 font-bold")
                    ui.label(f"Retenção Estimada: {r_pct}%").classes(f"px-2.5 py-0.5 rounded-full border font-extrabold {r_badge_cls}")

                with ui.row().classes("items-center gap-3 text-slate-600"):
                    ui.label(f"Estabilidade: {telem.current_stability:.1f}d")
                    ui.label(f"Dificuldade: {telem.current_difficulty:.1f}/10")
                    ui.label(f"Estado: {state_label} (Reps: {telem.repetitions})").classes("text-slate-400 font-medium")

        # Front side
        with ui.column().classes("w-full gap-2 my-2 p-4 bg-slate-50/70 rounded-2xl border border-slate-200/60"):
            ui.label("PERGUNTA / CONCEITO").classes("text-xs font-extrabold text-teal-800 tracking-widest")
            ui.label(front_clean).classes("text-slate-900 text-xl font-extrabold heading-font leading-snug whitespace-pre-wrap")

        if not session.reveal_flashcard:
            def reveal() -> None:
                session.reveal_flashcard = True
                save_session(session)
                refresh()
            ui.button("Mostrar Resposta (Verso)  [Espaço]", icon="visibility", on_click=reveal).props("color=primary size=lg").classes("w-full rounded-xl font-bold shadow-md my-4 py-3")
            return

        ui.separator().classes("my-2")

        # Back side revealed
        with ui.column().classes("w-full gap-2 bg-emerald-50/40 p-5 rounded-2xl border border-emerald-200/80 shadow-xs"):
            ui.label("RESPOSTA / EXPLICAÇÃO").classes("text-xs font-extrabold text-emerald-800 tracking-widest")
            ui.label(back_clean).classes("text-slate-900 text-base font-semibold leading-relaxed whitespace-pre-wrap")

        _render_mnemonic_forge(f"Front: {front_clean}\nBack: {back_clean}", session, refresh, sistema=raw_system)

        # AI Tutor Query Option
        with ui.column().classes("w-full gap-2 my-2 bg-indigo-50/60 p-4 rounded-xl border border-indigo-150"):
            with ui.row().classes("items-center justify-between w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("auto_awesome", size="18px").classes("text-indigo-600")
                    ui.label("Perguntar ao Tutor Gemini").classes("font-bold text-indigo-950 text-sm")
                is_socratic = ui.checkbox("Modo Socrático 🏛️ (Perguntas Guiadas)").classes("text-xs text-indigo-900 font-semibold")

            doubt_input = ui.input(placeholder="Dúvida específica sobre este conceito...").classes("w-full")

            if not ai_is_configured():
                ui.label("Tutor indisponível: configure a chave Gemini nas Configurações.").classes("text-xs text-slate-500")
            else:
                tutor_status = ui.row().classes("items-center gap-2 px-2")

                async def ask() -> None:
                    btn_ask.disable()
                    tutor_status.clear()
                    with tutor_status:
                        ui.spinner("dots", size="sm", color="indigo")
                        ui.label("Consultando Tutor Gemini...").classes("text-xs text-indigo-800 font-semibold animate-pulse")
                    try:
                        c_front = card.get("front", "")
                        c_back = card.get("back", "")
                        prompt_ctx = f"Front: {c_front}\nBack: {c_back}"
                        user_doubt = doubt_input.value or ""
                        if is_socratic.value:
                            res = await run.io_bound(StudyWorkflowService().ask_socratic, prompt_ctx, user_doubt)
                        else:
                            res = await run.io_bound(StudyWorkflowService().ask_tutor, prompt_ctx, user_doubt)
                        session.tutor_response = res
                        save_session(session)
                        refresh()
                    except (StudyApplicationError, Exception) as error:
                        ui.notify(str(error), type="negative")
                    finally:
                        btn_ask.enable()
                        tutor_status.clear()

                btn_ask = ui.button("Esclarecer com IA", icon="send", on_click=ask).props("flat color=indigo").classes("font-bold text-xs")
                tutor_status

        if session.tutor_response:
            with ui.card().classes("w-full p-4 bg-indigo-100/70 border border-indigo-300 rounded-xl gap-2"):
                ui.label("Resposta do Tutor Gemini").classes("font-bold text-indigo-950 text-xs uppercase")
                ui.markdown(session.tutor_response).classes("text-indigo-900 text-sm")
                tutor_card_status = ui.row().classes("items-center gap-2 px-2")

                async def tutor_cards() -> None:
                    btn_tutor_cards.disable()
                    tutor_card_status.clear()
                    with tutor_card_status:
                        ui.spinner("dots", size="sm", color="indigo")
                        ui.label("Gerando flashcards com a explicação do tutor...").classes("text-xs text-indigo-800 font-semibold animate-pulse")
                    try:
                        cards = await run.io_bound(StudyWorkflowService().generate_tutor_flashcards, session.tutor_response or "", card, session.draft_flashcards)
                        if not cards:
                            ui.notify("Nenhum flashcard gerado a partir da explicação.", type="warning")
                        else:
                            session.draft_flashcards.extend(cards)
                            save_session(session)
                            ui.notify(f"✨ {len(cards)} flashcard(s) gerado(s) a partir da explicação!", type="positive")
                            refresh()
                    except (StudyApplicationError, Exception) as error:
                        ui.notify(str(error), type="negative")
                    finally:
                        btn_tutor_cards.enable()
                        tutor_card_status.clear()

                btn_tutor_cards = ui.button("Criar Flashcard dessa Explicação", icon="add", on_click=tutor_cards).props("outline color=indigo").classes("rounded-xl font-semibold text-xs")
                tutor_card_status

        if session.draft_flashcards:
            card_tags = [t for t in card.get("tag_list", "").split("|") if t] if card.get("tag_list") else []
            _render_draft_flashcards_block(session, refresh, raw_system, card_tags)

        # FSRS Repetition Grading Section with Dynamic Previews
        ui.separator().classes("my-3")
        ui.label("Avalie a sua Lembrança (Agendamento FSRS v5)").classes("font-bold text-slate-900 text-sm heading-font text-center w-full tracking-wide")
        
        btn_configs = [
            (1, "Again [1]", "De novo", "bg-rose-50 hover:bg-rose-100 text-rose-900 border-rose-300"),
            (2, "Hard [2]", "Difícil", "bg-amber-50 hover:bg-amber-100 text-amber-900 border-amber-300"),
            (3, "Good [3]", "Bom", "bg-emerald-50 hover:bg-emerald-100 text-emerald-950 border-emerald-400 ring-2 ring-emerald-500/20"),
            (4, "Easy [4]", "Fácil", "bg-sky-50 hover:bg-sky-100 text-sky-900 border-sky-300"),
        ]
        with ui.row().classes("w-full gap-3 flex-wrap justify-center my-2"):
            for grade, title, desc, styles in btn_configs:
                rating_item = fsrs_preview.ratings[grade]
                
                def make_rate(value: int, r_item):
                    def _do_rate() -> None:
                        interval = review_flashcard(card, value, rating_preview=r_item)
                        grade_name = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}[value]
                        requeued = session.requeue_item(item, grade_name)
                        if value in (1, 2) and not requeued:
                            ui.notify("Limite de repetição nesta sessão atingido; o agendamento FSRS foi preservado.", type="info")
                        ui.notify(f"Agendado: {r_item.label} ({r_item.interval_display})", type="positive")
                        _next(session, refresh)
                    return _do_rate

                with ui.column().classes("flex-1 min-w-28 items-center"):
                    with ui.button(on_click=make_rate(grade, rating_item)).props("flat").classes(
                        f"w-full fsrs-btn border {styles} shadow-xs font-extrabold rounded-2xl py-2.5 transition-all transform active:scale-95"
                    ):
                        with ui.column().classes("items-center gap-0.5 leading-tight"):
                            ui.label(title).classes("text-xs font-extrabold")
                            ui.label(rating_item.interval_display).classes("text-sm font-black")
                            if grade == 3:
                                ui.label("[Espaço]").classes("text-[10px] text-emerald-700 font-semibold uppercase tracking-tighter")


def _render_mnemonic_forge(context_text: str, session, refresh, sistema: str = "General_Principles") -> None:
    if not ai_is_configured():
        return

    workflow = StudyWorkflowService()
    status_container = ui.row().classes("items-center gap-2 px-3")

    async def get_mnemonic() -> None:
        btn.disable()
        status_container.clear()
        with status_container:
            ui.spinner("dots", size="sm", color="amber")
            ui.label("Gerando mnemônico de alta retenção (Dual-Coding)...").classes("text-xs text-amber-800 font-semibold animate-pulse")
        try:
            res = await run.io_bound(workflow.generate_mnemonic, context_text, "🎨 Cena Visual (Dual-Coding)")
            session.mnemonic_response = res
            save_session(session)
            refresh()
        except (StudyApplicationError, Exception) as error:
            ui.notify(str(error), type="negative")
        finally:
            btn.enable()
            status_container.clear()

    with ui.row().classes("w-full items-center justify-between my-2 p-3 bg-amber-50/70 border border-amber-200 rounded-xl"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("lightbulb", size="20px").classes("text-amber-600")
            ui.label("Mnemônico Científico de Alta Retenção").classes("font-bold text-amber-950 text-sm")
        btn = ui.button("Gerar Mnemônico IA", icon="auto_awesome", on_click=get_mnemonic).props("flat color=amber").classes("font-bold text-xs")

    status_container

    if getattr(session, "mnemonic_response", None):
        with ui.card().classes("w-full p-4 bg-amber-50 border border-amber-300 rounded-xl gap-2 my-2"):
            with ui.row().classes("items-center justify-between border-b border-amber-200 pb-1"):
                ui.label("🧠 Mnemônico & Ancoragem Visual (IA)").classes("font-bold text-amber-950 text-xs uppercase tracking-wider")
            ui.markdown(session.mnemonic_response).classes("text-amber-900 text-sm font-medium leading-relaxed")

            def save_to_acervo() -> None:
                from core.repositories.mnemonic_repository import MnemonicRepository
                MnemonicRepository().salvar_mnemonico("Mnemônico IA (Sessão)", session.mnemonic_response or "", sistema)
                ui.notify("Mnemônico de alta retenção salvo no seu Acervo!", type="positive")

            ui.button("Salvar no Acervo de Mnemônicos", icon="bookmark", on_click=save_to_acervo).props("flat color=amber size=sm").classes("font-bold text-xs")


def _render_demystifier_forge(question: dict, session, refresh) -> None:
    if not ai_is_configured():
        return

    workflow = StudyWorkflowService()
    status_container = ui.row().classes("items-center gap-2 px-3")

    async def demystify() -> None:
        btn.disable()
        status_container.clear()
        with status_container:
            ui.spinner("dots", size="sm", color="blue")
            ui.label("Desmistificando distratores com IA...").classes("text-xs text-blue-800 font-semibold animate-pulse")
        try:
            res = await run.io_bound(workflow.demystify_distractors, question)
            session.demystified_response = res
            save_session(session)
            refresh()
        except (StudyApplicationError, Exception) as error:
            ui.notify(str(error), type="negative")
        finally:
            btn.enable()
            status_container.clear()

    with ui.row().classes("w-full items-center justify-between my-2 p-3 bg-blue-50/70 border border-blue-200 rounded-xl slide-up"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("find_in_page", size="20px").classes("text-blue-600")
            ui.label("Desmistificador de Distratores (Se Fosse Outra Doença...)").classes("font-bold text-blue-950 text-sm")
        btn = ui.button("Desmistificar", icon="psychology", on_click=demystify).props("flat color=blue").classes("font-bold text-xs")

    status_container

    if getattr(session, "demystified_response", None):
        with ui.card().classes("w-full p-4 bg-blue-50 border border-blue-300 rounded-xl gap-2 my-2 fade-in"):
            ui.label("🔍 Diagnóstico Diferencial Reverso das Alternativas").classes("font-bold text-blue-950 text-xs uppercase tracking-wider border-b border-blue-200 pb-1")
            ui.markdown(session.demystified_response).classes("text-blue-900 text-sm font-medium leading-relaxed")


def _render_pearl_forge(context_text: str, sistema: str, session, refresh) -> None:
    if not ai_is_configured():
        return

    workflow = StudyWorkflowService()
    status_container = ui.row().classes("items-center gap-2 px-3")

    async def get_pearl() -> None:
        btn.disable()
        status_container.clear()
        with status_container:
            ui.spinner("dots", size="sm", color="emerald")
            ui.label("Extraindo pérola com IA...").classes("text-xs text-emerald-800 font-semibold animate-pulse")
        try:
            res = await run.io_bound(workflow.extract_pearl, context_text)
            session.pearl_response = res
            save_session(session)
            refresh()
        except (StudyApplicationError, Exception) as error:
            ui.notify(str(error), type="negative")
        finally:
            btn.enable()
            status_container.clear()

    with ui.row().classes("w-full items-center justify-between my-2 p-3 bg-emerald-50/70 border border-emerald-200 rounded-xl"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("diamond", size="20px").classes("text-emerald-600")
            ui.label("Extrair Pérola High-Yield (1 Frase)").classes("font-bold text-emerald-950 text-sm")
        btn = ui.button("Extrair Pérola", icon="auto_awesome", on_click=get_pearl).props("flat color=emerald").classes("font-bold text-xs")

    status_container

    if getattr(session, "pearl_response", None):
        with ui.card().classes("w-full p-4 bg-emerald-100/80 border border-emerald-300 rounded-xl gap-2 my-2"):
            ui.markdown(session.pearl_response).classes("text-emerald-950 text-sm font-extrabold")

            def save_pearl_to_db() -> None:
                workflow.save_pearl(session.pearl_response or "", sistema)
                ui.notify("Pérola salva no Caderno de Pérolas (Histórico)!", type="positive")

            ui.button("Salvar no Caderno de Pérolas", icon="bookmark", on_click=save_pearl_to_db).props("flat color=emerald size=sm").classes("font-bold text-xs")



