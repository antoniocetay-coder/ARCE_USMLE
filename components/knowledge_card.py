from __future__ import annotations

import re
from nicegui import ui

from core.repositories.knowledge_repository import (
    KnowledgeNodeData,
    KnowledgeRepository,
)


def get_ontology_badge_class(ontology_type: str) -> str:
    low = ontology_type.lower()
    if "disease" in low or "condition" in low:
        return "ontology-badge-disease"
    if "drug" in low or "treatment" in low:
        return "ontology-badge-drug"
    if "gene" in low or "dna" in low or "rna" in low:
        return "ontology-badge-gene"
    if "receptor" in low or "channel" in low:
        return "ontology-badge-receptor"
    if "pathway" in low or "process" in low:
        return "ontology-badge-pathway"
    if "test" in low or "diagnostic" in low:
        return "ontology-badge-test"
    if "finding" in low or "sign" in low or "symptom" in low:
        return "ontology-badge-finding"
    return "ontology-badge-default"


def clean_snippet(text: str) -> str:
    """Limpa tags de comentários Markdown e cabeçalhos brutais para visualização no card."""
    t = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    t = re.sub(r"_Source:.*?;?", "", t)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^!\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def open_node_detail_dialog(node: KnowledgeNodeData, on_select=None) -> None:
    """Abre um modal detalhado com a fundamentação RAG completa e conexões ontológicas."""
    ont_type = getattr(node, "ontology_type", "") or ""
    badge_cls = get_ontology_badge_class(ont_type)

    with ui.dialog() as dialog, ui.card().classes("p-6 rounded-3xl max-w-3xl w-full gap-4 max-h-[85vh] overflow-y-auto bg-white border border-slate-200 shadow-xl"):
        with ui.row().classes("items-center justify-between w-full border-b border-slate-100 pb-3"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("hub", size="28px").classes("text-sky-600")
                with ui.column().classes("gap-0"):
                    ui.label(getattr(node, "title", "Conceito")).classes("text-2xl font-extrabold text-slate-900 heading-font tracking-tight")
                    ui.label(f"ID do Nó: {getattr(node, 'node_id', '')} · Categoria: {getattr(node, 'folder_category', '')}").classes("text-xs text-slate-500 font-semibold")
            ui.label(ont_type).classes(f"ontology-badge {badge_cls}")

        aliases = getattr(node, "aliases", []) or []
        if aliases:
            with ui.row().classes("items-center gap-2 bg-slate-50 p-3 rounded-xl border border-slate-100 w-full"):
                ui.label("Sinônimos & Aliases:").classes("text-xs font-bold text-slate-500 uppercase tracking-wider")
                for alias in aliases:
                    ui.label(alias).classes("bg-white border border-slate-200 text-slate-700 px-2.5 py-0.5 rounded-lg text-xs font-medium")

        # Conexões Ontológicas do Nó
        from core.algorithms.ontology_brain import OntologyBrain
        brain = OntologyBrain()
        relations = brain.get_clinical_relations(getattr(node, "title", ""))
        has_relations = any(relations.values()) if relations else False

        if has_relations:
            with ui.card().classes("w-full p-4 bg-sky-50/60 border border-sky-200/80 rounded-2xl gap-2"):
                ui.label("🌐 Conexões Ontológicas na Malha Clínica").classes("text-xs font-extrabold text-sky-950 uppercase tracking-wider mb-1")
                with ui.row().classes("w-full gap-3 flex-wrap text-xs"):
                    if relations.get("PREREQUISITE_FOR"):
                        with ui.column().classes("gap-1 bg-white p-2.5 rounded-xl border border-sky-100 flex-1 min-w-44"):
                            ui.label("Pré-requisitos / Conexões:").classes("font-bold text-sky-900 text-[11px]")
                            for p in relations["PREREQUISITE_FOR"][:4]:
                                ui.label(f"• {p}").classes("text-slate-700 font-medium")
                    if relations.get("CAUSES"):
                        with ui.column().classes("gap-1 bg-white p-2.5 rounded-xl border border-sky-100 flex-1 min-w-44"):
                            ui.label("Causas / Relações:").classes("font-bold text-rose-900 text-[11px]")
                            for c in relations["CAUSES"][:4]:
                                ui.label(f"• {c}").classes("text-slate-700 font-medium")
                    if relations.get("MANIFESTS_AS"):
                        with ui.column().classes("gap-1 bg-white p-2.5 rounded-xl border border-sky-100 flex-1 min-w-44"):
                            ui.label("Manifesta-se como:").classes("font-bold text-emerald-900 text-[11px]")
                            for m in relations["MANIFESTS_AS"][:4]:
                                ui.label(f"• {m}").classes("text-slate-700 font-medium")

        # Fragmentos RAG
        ui.label("Fragmentos de Conhecimento Obsidian (Fundamentação RAG)").classes("font-bold text-slate-900 text-sm heading-font mt-2")
        fragments = getattr(node, "fragments", []) or []
        if fragments:
            for idx, frag in enumerate(fragments):
                with ui.column().classes("w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl gap-2 my-1"):
                    with ui.row().classes("items-center justify-between w-full border-b border-slate-200/80 pb-2 text-xs"):
                        ui.label(f"Fragmento #{idx + 1} · {getattr(frag, 'source_chunk', None) or 'Obsidian Note'}").classes("font-bold text-slate-800")
                        if getattr(frag, "source_lines", None):
                            ui.label(f"Linhas {frag.source_lines}").classes("text-slate-400 font-semibold")
                    cleaned = clean_snippet(getattr(frag, "content", ""))
                    ui.markdown(cleaned).classes("text-slate-800 text-xs leading-relaxed font-sans")
        else:
            ui.label("Nenhum fragmento de texto detalhado associado a este nó.").classes("text-slate-400 italic text-xs")

        with ui.row().classes("w-full justify-between items-center pt-4 border-t border-slate-100 mt-2"):
            ui.button("Fechar", on_click=dialog.close).props("flat color=slate").classes("font-semibold text-xs")
            if on_select:
                async def do_select() -> None:
                    dialog.close()
                    import inspect
                    if inspect.iscoroutinefunction(on_select):
                        await on_select(node)
                    else:
                        res = on_select(node)
                        if inspect.isawaitable(res):
                            await res
                ui.button("Praticar Nó com IA (Questão NBME)", icon="bolt", on_click=do_select).props("color=sky size=md").classes("rounded-xl font-bold px-5 text-xs shadow-md")

    dialog.open()


def render_knowledge_node_card(node: KnowledgeNodeData, on_select=None) -> None:
    """Renderiza um card moderno, limpo e elegante para o Obsidian Knowledge Vault."""
    ont_type = getattr(node, "ontology_type", "") or ""
    badge_cls = get_ontology_badge_class(ont_type)

    with ui.card().classes("obsidian-card w-full p-5 gap-3 cursor-pointer card-hover-lift").on("click", lambda *_: open_node_detail_dialog(node, on_select)):
        with ui.row().classes("items-center justify-between w-full"):
            with ui.row().classes("items-center gap-2.5"):
                with ui.row().classes("w-8 h-8 rounded-xl bg-sky-100 text-sky-700 items-center justify-center font-bold border border-sky-200/80"):
                    ui.icon("description", size="18px")
                ui.label(getattr(node, "title", "Conceito")).classes("font-extrabold text-slate-900 text-base heading-font tracking-tight")

            ui.label(ont_type).classes(f"ontology-badge {badge_cls}")

        aliases = getattr(node, "aliases", []) or []
        if aliases:
            with ui.row().classes("items-center gap-1 flex-wrap py-0.5"):
                for alias in aliases[:3]:
                    ui.label(alias).classes("bg-slate-100 text-slate-600 border border-slate-200/60 px-2 py-0.5 rounded-md text-[11px] font-medium")

        fragments = getattr(node, "fragments", []) or []
        if fragments:
            first_frag = fragments[0]
            snippet = clean_snippet(getattr(first_frag, "content", ""))
            if len(snippet) > 180:
                snippet = snippet[:180] + "..."

            with ui.column().classes("w-full bg-slate-50/90 border border-slate-200/70 p-3 rounded-xl gap-1 text-xs text-slate-700 font-sans leading-relaxed"):
                ui.label(snippet).classes("text-slate-600 text-xs leading-normal")

        with ui.row().classes("items-center justify-between w-full pt-2 border-t border-slate-100 mt-1"):
            with ui.row().classes("items-center gap-2 text-xs text-slate-400 font-medium"):
                ui.icon("folder", size="16px").classes("text-slate-400")
                ui.label(f"{getattr(node, 'folder_category', '')}")

            with ui.row().classes("items-center gap-2"):
                ui.button("Ver Detalhes", icon="visibility", on_click=lambda: open_node_detail_dialog(node, on_select)).props("flat color=sky size=xs stop").classes("font-bold text-xs")
                if on_select:
                    async def do_card_select() -> None:
                        import inspect
                        if inspect.iscoroutinefunction(on_select):
                            await on_select(node)
                        else:
                            res = on_select(node)
                            if inspect.isawaitable(res):
                                await res
                    ui.button("Praticar", icon="bolt", on_click=do_card_select).props("color=teal size=xs flat stop").classes("font-bold text-xs")
