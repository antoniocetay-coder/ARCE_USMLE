from __future__ import annotations

from collections.abc import Iterable


def formatar_contexto_redundancia(cards_banco: Iterable[dict], cards_rascunho: Iterable[dict]) -> str:
    cards = [*cards_banco, *cards_rascunho]
    if not cards:
        return "EXISTING FLASHCARDS: none."
    lines = [f"- Q: {card.get('front', '')}" for card in cards[:20]]
    return "EXISTING FLASHCARDS (do not repeat these facts):\n" + "\n".join(lines)


def construir_prompt_analitico(
    vignette: str,
    objective: str,
    correct: str,
    correct_explanation: str,
    selected: str,
    selected_explanation: str,
    context: str,
    target_count: int | None = None,
) -> str:
    if target_count:
        count_instruction = f"GENERATE EXACTLY {target_count} MICRO-ATOMIC FLASHCARDS."
    else:
        count_instruction = "DECOMPOSE EXHAUSTIVELY INTO AS MANY MICRO-ATOMIC FLASHCARDS AS NEEDED (typically 6 to 15+ cards). Split every single fact into its own tiny card."

    return f"""You are an elite USMLE Anki & SuperMemo master author who strictly follows the 20 Rules of Formulating Knowledge.
The student answered a question incorrectly or had a doubt. Your task is to take the medical concepts and BREAK THEM DOWN INTO MICRO-ATOMIC, BITE-SIZED FLASHCARDS.

QUESTION VIGNETTE:
{vignette}

EDUCATIONAL OBJECTIVE:
{objective}

CORRECT ANSWER ({correct}):
{correct_explanation}

STUDENT'S INCORRECT CHOICE ({selected}):
{selected_explanation}

{context}

CRITICAL FLASHCARD HYGIENE RULES (MINIMUM INFORMATION PRINCIPLE):
1. THE 3-SECOND RULE (BITE-SIZED & INSTANT):
   - Each card must test EXACTLY ONE single, indivisible retrieval target that can be answered in under 3 seconds.
   - FRONT: Maximum 1 short, razor-sharp sentence (10-18 words max).
   - BACK: Ultra-concise (1 to 8 words maximum, or 1 brief sentence).

2. FORBIDDEN ANTI-PATTERNS (DO NOT DO THIS):
   - STRICTLY FORBIDDEN: Compound/multi-part questions (e.g. "What is X AND how does it differ from Y?"). NEVER ask two things in one card!
   - STRICTLY FORBIDDEN: Vignette-length questions (e.g. "A 54-year-old patient presents with... and dies 3 hours later, what happens at 12-24h?").
   - STRICTLY FORBIDDEN: Paragraph-long essay answers or "Context:" footers on the back.

3. HOW TO PROPERLY DECOMPOSE (EXAMPLE STUDY):
   If the topic is "Myocardial Infarction Necrosis & Histopathology vs Brain Ischemia", DO NOT create 1 or 2 big cards. SPLIT IT INTO 6 CRISP MICRO-CARDS:
   - Card 1: Front: "Which necrosis pattern occurs in myocardial infarction (and most solid organs)?" -> Back: "Coagulative necrosis."
   - Card 2: Front: "What is the hallmark microscopic feature of coagulative necrosis?" -> Back: "Preserved cell outlines (ghost cells) with loss of nuclei."
   - Card 3: Front: "Which necrosis pattern is uniquely characteristic of ischemic brain infarction (stroke)?" -> Back: "Liquefactive necrosis (enzymatic digestion by microglia)."
   - Card 4: Front: "In myocardial infarction, what histological change appears within 12 to 24 hours?" -> Back: "Early coagulative necrosis, contraction bands, and hypereosinophilia."
   - Card 5: Front: "In myocardial infarction, which inflammatory cell predominates at 1 to 3 days post-infarct?" -> Back: "Neutrophils."
   - Card 6: Front: "In myocardial infarction, which cell type predominates at 3 to 7 days post-infarct?" -> Back: "Macrophages (phagocytosing necrotic debris)."

4. TASK & QUANTITY:
   {count_instruction}
   Deconstruct the underlying pathophysiology, receptors, pharmacology, histopathology, timelines, and clinical discriminators into clean, separate micro-cards.

5. FORMAT:
   - Plain clean text only (NO **, *, #, bullets).
   - Strictly in English.
   - Return ONLY valid JSON in this exact structure:

{{
    "cards": [
        {{
            "front": "Short, razor-sharp direct question?",
            "back": "Ultra-concise single target answer.",
            "tags": ["Targeted_Decomposition"]
        }}
    ]
}}
"""