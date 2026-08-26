from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import app, ui

from ai.settings import load_ai_settings
from config import APP_NAME
from state.study_session import StudySession


def load_session() -> StudySession:
    return StudySession.from_dict(app.storage.user.get("study_session"))


def save_session(session: StudySession) -> None:
    app.storage.user["study_session"] = session.to_dict()


def ai_is_configured() -> bool:
    return load_ai_settings().api_key is not None


@contextmanager
def page_layout(title: str, active_path: str) -> Iterator[None]:
    ui.add_head_html('<link rel="stylesheet" href="/static/styles.css">')
    ui.colors(primary="#003B36", secondary="#064E3B", accent="#10B981")


    # Dark Emerald Left Sidebar (High Contrast Text & Icons)
    with ui.left_drawer(value=True).classes("app-drawer flex flex-col justify-between py-6 px-0 w-64 border-none shadow-lg"):
        with ui.column().classes("w-full gap-6"):
            # Logo Header
            with ui.row().classes("items-center gap-3 px-6 pt-2"):
                with ui.row().classes("w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-400/40 text-emerald-400 items-center justify-center"):
                    ui.icon("local_pharmacy", size="22px").classes("text-emerald-400")
                ui.label("ARC-e USMLE").classes("text-xl font-extrabold tracking-tight text-white heading-font")

            # Nav Links
            with ui.column().classes("w-full gap-1 mt-2"):
                links = [
                    ("/", "Dashboard", "grid_view"),
                    ("/study", "Estudo", "school"),
                    ("/targeted-practice", "Prática direcionada", "track_changes"),
                    ("/knowledge-vault", "Knowledge Vault", "hub"),
                    ("/mnemonics", "Mnemônicos", "lightbulb"),
                    ("/analytics", "Analytics", "show_chart"),
                    ("/history", "Histórico", "history"),
                    ("/settings", "Configurações", "settings")
                ]





                def make_nav(target_path: str):
                    return lambda: ui.navigate.to(target_path)

                for path, label, icon in links:
                    is_active = active_path == path
                    btn = ui.button(label, icon=icon, on_click=make_nav(path)).props("flat align=left")
                    btn.classes("nav-active" if is_active else "nav-link")

        # Bottom Section: Progress Card & User Profile Footer
        with ui.column().classes("w-full px-4 gap-4 pb-2"):
            # Sidebar Analytics Progress Card
            with ui.card().classes("w-full p-4 rounded-2xl bg-white/10 border border-white/20 text-white gap-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("show_chart", size="18px").classes("text-emerald-400")
                    ui.label("Acompanhe seu progresso").classes("text-xs font-extrabold text-white")
                ui.label("Veja estatísticas detalhadas e evolua todos os dias.").classes("text-xs text-slate-200 leading-tight")
                
                # High-contrast bright mint green button link
                btn_analytics = ui.button("Abrir Analytics →", on_click=lambda: ui.navigate.to("/analytics")).props("flat").classes("p-0 font-extrabold text-xs cursor-pointer mt-1")
                btn_analytics.style("color: #34D399 !important; font-weight: 800 !important;")

            # User Footer Profile
            with ui.row().classes("w-full items-center justify-between pt-3 border-t border-white/15 px-2"):
                with ui.row().classes("items-center gap-3"):
                    with ui.row().classes("w-9 h-9 rounded-full bg-emerald-500/30 text-emerald-300 font-extrabold items-center justify-center text-sm border border-emerald-400/40"):
                        ui.label("A")
                    with ui.column().classes("gap-0"):
                        ui.label("Antônio").classes("text-sm font-extrabold text-white leading-tight")
                        ui.label("Estudante").classes("text-xs text-slate-300 font-semibold")
                ui.icon("keyboard_arrow_down", size="18px").classes("text-slate-300 cursor-pointer")

    # Main Content Area (With Top-Right Header Bar Inside)
    with ui.column().classes("page-content w-full max-w-7xl mx-auto p-6 md:p-8 gap-6"):
        # Top Header Bar (AI Status Badge, Notifications & User Avatar)
        with ui.row().classes("w-full justify-between items-center gap-4 mb-2 border-b border-slate-200/60 pb-3"):
            # Live AI Status Badge
            ai_active = ai_is_configured()
            status_bg = "bg-emerald-50 border-emerald-200 text-emerald-900" if ai_active else "bg-slate-100 border-slate-200 text-slate-600"
            status_text = "IA Gemini Conectada" if ai_active else "Modo Offline (Sem Chave)"

            with ui.row().classes(f"items-center gap-2 text-xs font-bold px-3 py-1.5 rounded-full border {status_bg} shadow-2xs"):
                if ai_active:
                    ui.html('<span class="ai-pulse-dot"></span>')
                else:
                    ui.icon("wifi_off", size="14px").classes("text-slate-400")
                ui.label(status_text)

            with ui.row().classes("items-center gap-3"):
                dark_mode = ui.dark_mode(value=app.storage.user.get("dark_mode", False))
                
                def toggle_dark():
                    dark_mode.value = not dark_mode.value
                    app.storage.user["dark_mode"] = dark_mode.value

                ui.button(icon="dark_mode", on_click=toggle_dark).props("flat round dense size=sm").classes("text-slate-700")

                with ui.row().classes("relative cursor-pointer p-1.5 rounded-full hover:bg-slate-200/50"):
                    ui.icon("notifications", size="22px").classes("text-slate-700")
                    ui.label("").classes("w-2 h-2 rounded-full bg-emerald-500 absolute top-1 right-1 border border-white")

                with ui.row().classes("items-center gap-2 bg-slate-100/80 hover:bg-slate-200/80 py-1 px-2.5 rounded-full cursor-pointer transition-all border border-slate-200/60"):
                    with ui.row().classes("w-7 h-7 rounded-full bg-[#003B36] text-white font-extrabold items-center justify-center text-xs"):
                        ui.label("A")
                    ui.icon("keyboard_arrow_down", size="16px").classes("text-slate-600")

        yield

