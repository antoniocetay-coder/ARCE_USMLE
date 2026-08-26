from __future__ import annotations

import json
import logging
import re
from typing import Any

from ai.client import generate_text
from ai.settings import load_ai_settings
from core.ai.flashcard_prompts import (
    construir_prompt_analitico,
    formatar_contexto_redundancia,
)
from core.ai.legacy_validation import limpar_json
from core.exceptions import FlashcardGenerationError

logger = logging.getLogger(__name__)


def strip_markdown(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"Metacognitive\s*(Cure)?:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = cleaned.replace("**", "").replace("*", "")
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _text_similarity(a: str, b: str) -> float:
    words_a = set(re.findall(r"\w+", a.lower()))
    words_b = set(re.findall(r"\w+", b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a.intersection(words_b)
    union = words_a.union(words_b)
    return len(intersection) / len(union) if union else 0.0


def deduplicate_card_list(cards: list[dict], threshold: float = 0.80) -> list[dict]:
    unique: list[dict] = []
    for card in cards:
        front = card.get("front", "")
        back = card.get("back", "")
        is_dup = False
        for u in unique:
            f_sim = _text_similarity(front, u.get("front", ""))
            b_sim = _text_similarity(back, u.get("back", ""))
            if f_sim >= threshold and b_sim >= threshold:
                is_dup = True
                break
            if f_sim >= 0.90:  # virtually identical question
                is_dup = True
                break
        if not is_dup:
            unique.append(card)
    return unique


def sanitize_card_list(cards: list[dict]) -> list[dict]:
    sanitized = []
    for c in cards:
        if isinstance(c, dict):
            front = c.get("front") or c.get("question") or c.get("prompt") or c.get("frente") or c.get("pergunta") or ""
            back = c.get("back") or c.get("answer") or c.get("response") or c.get("verso") or c.get("resposta") or ""
            tags = c.get("tags") or c.get("tag_list") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split("|") if t.strip()]
            f_clean = strip_markdown(str(front)).strip()
            b_clean = strip_markdown(str(back)).strip()
            if f_clean and b_clean:
                sanitized.append({
                    "front": f_clean,
                    "back": b_clean,
                    "tags": tags if isinstance(tags, list) else [],
                })
    return deduplicate_card_list(sanitized)


def parse_flashcards_response(texto_bruto: str) -> list[dict]:
    cleaned = limpar_json(texto_bruto)
    try:
        data = json.loads(cleaned if cleaned else texto_bruto, strict=False)
    except Exception as e:
        try:
            sanitized_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', cleaned if cleaned else texto_bruto)
            data = json.loads(sanitized_text, strict=False)
        except Exception:
            logger.warning("parse_flashcards_response json.loads failed: %s | raw: %s", e, texto_bruto)
            return []

    if isinstance(data, list):
        res = sanitize_card_list(data)
        logger.info("parse_flashcards_response extracted %d cards from list", len(res))
        return res
    if isinstance(data, dict):
        for key in ("cards", "flashcards", "items", "data", "cards_rascunho", "flashcard_list", "questions"):
            for k_candidate in (key, key.upper(), key.capitalize()):
                val = data.get(k_candidate)
                if isinstance(val, list):
                    res = sanitize_card_list(val)
                    if res:
                        logger.info("parse_flashcards_response extracted %d cards from key '%s'", len(res), k_candidate)
                        return res
        front = data.get("front") or data.get("question") or data.get("prompt")
        back = data.get("back") or data.get("answer") or data.get("response")
        if front and back:
            res = sanitize_card_list([data])
            logger.info("parse_flashcards_response extracted single card from dict")
            return res
        sub_dicts = [v for v in data.values() if isinstance(v, dict)]
        if sub_dicts:
            res = sanitize_card_list(sub_dicts)
            if res:
                logger.info("parse_flashcards_response extracted %d cards from nested dict values", len(res))
                return res

    logger.warning("parse_flashcards_response: could not extract valid cards from data: %s", data)
    return []


def orquestrar_flashcards(
    questao: dict[str, Any],
    letra_marcada: str,
    acertou: bool,
    confianca: str,
    cards_banco: list[dict[str, Any]],
    cards_rascunho: list[dict[str, Any]],
    target_count: int | None = None,
) -> list[dict[str, Any]]:
    edu_obj = questao.get("educational_objective", "")
    correct_opt = questao.get("correct", "")
    explanations = questao.get("explanations", {})
    correct_exp = explanations.get(correct_opt, "No explanation provided.")
    wrong_exp = explanations.get(letra_marcada, "No explanation provided.")

    block_redundancia = formatar_contexto_redundancia(cards_banco, cards_rascunho)
    vignette = questao.get("vignette", "")

    prompt = construir_prompt_analitico(
        vignette=vignette,
        objective=edu_obj,
        correct=correct_opt,
        correct_explanation=correct_exp,
        selected=letra_marcada,
        selected_explanation=wrong_exp,
        context=block_redundancia,
        target_count=target_count,
    )

    try:
        texto_bruto = generate_text(prompt, load_ai_settings().flashcard_model, response_json=True)
        return parse_flashcards_response(texto_bruto)
    except Exception as error:
        raise FlashcardGenerationError("Não foi possível gerar flashcards de intervenção.") from error


def gerar_mais_flashcards(
    questao: dict[str, Any],
    cards_banco: list[dict[str, Any]],
    cards_rascunho: list[dict[str, Any]],
    target_count: int | None = None,
) -> list[dict[str, Any]]:
    edu_obj = questao.get("educational_objective", "")
    block_redundancia = formatar_contexto_redundancia(cards_banco, cards_rascunho)
    count_instruction = f"GENERATE EXACTLY {target_count} MICRO-ATOMIC CARDS." if target_count else "DECOMPOSE INTO AS MANY MICRO-ATOMIC CARDS AS NEEDED (6 to 12+ cards)."

    prompt = f"""You are an elite USMLE Anki & SuperMemo author (following the 20 Rules of Formulating Knowledge).
The student wants to explore THIS SAME TOPIC in depth. Break the topic into BITE-SIZED, 3-SECOND MICRO-FLASHCARDS.

EDUCATIONAL OBJECTIVE: {edu_obj}

{block_redundancia}

STRICT FLASHCARD HYGIENE RULES:
1. 3-SECOND ANSWERABILITY:
   - FRONT: 1 short, razor-sharp sentence (10-18 words max).
   - BACK: Ultra-concise (1-8 words max, or 1 crisp sentence).
2. NO COMPOUND QUESTIONS:
   - NEVER ask two things in one card (no "and how does...", "describe the difference").
   - NEVER write mini clinical vignettes on the front or paragraphs on the back.
3. TASK:
   {count_instruction}
   Split every single fact (clinical presentation, pathophysiology, diagnostic tests, 1st-line drugs, contraindications) into its own separate card!
4. LANGUAGE & FORMAT:
   - Plain clean text only (no **, *, #). Strictly in English.

FORMAT (JSON only):
{{
    "cards": [
        {{
            "front": "Short razor-sharp question?",
            "back": "Ultra-concise single target answer.",
            "tags": ["Topic_Expansion"]
        }}
    ]
}}
"""
    try:
        texto_bruto = generate_text(prompt, load_ai_settings().flashcard_model, response_json=True)
        return parse_flashcards_response(texto_bruto)
    except Exception as error:
        raise FlashcardGenerationError("Não foi possível expandir os flashcards.") from error


def gerar_flashcard_sob_demanda(
    questao: dict[str, Any],
    pedido_usuario: str,
    cards_banco: list[dict[str, Any]],
    cards_rascunho: list[dict[str, Any]],
    target_count: int | None = None,
) -> list[dict[str, Any]]:
    edu_obj = questao.get("educational_objective", "")
    opcoes = "\n".join(questao.get("options", []))
    explanations = json.dumps(questao.get("explanations", {}), indent=2)
    block_redundancia = formatar_contexto_redundancia(cards_banco, cards_rascunho)
    count_instruction = f"GENERATE EXACTLY {target_count} MICRO-ATOMIC CARDS." if target_count else "GENERATE AS MANY MICRO-ATOMIC CARDS AS NEEDED (4 to 8+ cards)."

    prompt = f"""You are an elite USMLE Anki & SuperMemo author (following the 20 Rules of Formulating Knowledge).

QUESTION CONTEXT:
Objective: {edu_obj}
Options: {opcoes}
Explanations: {explanations}

STUDENT'S SPECIFIC REQUEST / DOUBT:
"{pedido_usuario}"

{block_redundancia}

STRICT FLASHCARD HYGIENE RULES:
1. 3-SECOND ANSWERABILITY:
   - FRONT: 1 short, razor-sharp sentence (10-18 words max).
   - BACK: Ultra-concise (1-8 words max, or 1 crisp sentence).
2. NO COMPOUND QUESTIONS:
   - NEVER ask two things in one card.
   - NEVER write paragraphs or "Context:" footers on the back.
3. TASK:
   {count_instruction}
   Deconstruct the student's doubt into discrete, bite-sized micro-cards.
4. Plain clean text only, strictly in English.

FORMAT (JSON only):
{{
    "cards": [
        {{
            "front": "Short razor-sharp question?",
            "back": "Ultra-concise single target answer.",
            "tags": ["Targeted_Review"]
        }}
    ]
}}
"""
    try:
        texto_bruto = generate_text(prompt, load_ai_settings().flashcard_model, response_json=True)
        return parse_flashcards_response(texto_bruto)
    except Exception as error:
        raise FlashcardGenerationError("Não foi possível gerar o flashcard solicitado.") from error


def gerar_flashcard_por_reflexao_erro(
    questao: dict[str, Any],
    reflexao_usuario: str,
    letra_marcada: str,
    acertou: bool,
    cards_banco: list[dict[str, Any]],
    cards_rascunho: list[dict[str, Any]],
    target_count: int | None = None,
) -> list[dict[str, Any]]:
    edu_obj = questao.get("educational_objective", "")
    correct_opt = questao.get("correct", "")
    explanations = questao.get("explanations", {})
    correct_exp = explanations.get(correct_opt, "")
    selected_exp = explanations.get(letra_marcada, "")
    vignette = questao.get("vignette", "")
    block_redundancia = formatar_contexto_redundancia(cards_banco, cards_rascunho)

    if target_count:
        count_instruction = f"GENERATE EXACTLY {target_count} MICRO-ATOMIC FLASHCARDS."
    else:
        count_instruction = "DECOMPOSE INTO AS MANY MICRO-ATOMIC FLASHCARDS AS NEEDED (typically 6 to 15+ cards). Split every single fact into its own tiny card."

    prompt = f"""You are an elite USMLE Anki & SuperMemo author who strictly follows the 20 Rules of Formulating Knowledge.
The student made an error or had a doubt on this clinical question:

STUDENT'S REFLECTION ON THEIR ERROR / DOUBT:
"{reflexao_usuario}"

VIGNETTE CONTEXT: {vignette}
EDUCATIONAL OBJECTIVE: {edu_obj}
CORRECT OPTION ({correct_opt}): {correct_exp}
SELECTED OPTION ({letra_marcada}): {selected_exp}

{block_redundancia}

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
            "tags": ["Error_Refinement"]
        }}
    ]
}}
"""
    try:
        texto_bruto = generate_text(prompt, load_ai_settings().flashcard_model, response_json=True)
        return parse_flashcards_response(texto_bruto)
    except Exception as error:
        raise FlashcardGenerationError("Não foi possível gerar o flashcard de reflexão de erro.") from error


def gerar_flashcards_do_tutor(
    explicacao: str,
    cards_banco: list[dict[str, Any]],
    cards_rascunho: list[dict[str, Any]],
    target_count: int | None = None,
) -> list[dict[str, Any]]:
    block_redundancia = formatar_contexto_redundancia(cards_banco, cards_rascunho)
    count_instruction = f"GENERATE EXACTLY {target_count} MICRO-ATOMIC CARDS." if target_count else "DECOMPOSE INTO AS MANY MICRO-ATOMIC CARDS AS NEEDED (4 to 8+ cards)."

    prompt = f"""You are an expert USMLE Anki & SuperMemo author.
A tutor just provided this clinical explanation:

TUTOR'S EXPLANATION:
{explicacao}

{block_redundancia}

STRICT FLASHCARD HYGIENE RULES:
1. 3-SECOND ANSWERABILITY:
   - FRONT: 1 short, razor-sharp sentence (10-18 words max).
   - BACK: Ultra-concise (1-8 words max, or 1 crisp sentence).
2. NO COMPOUND QUESTIONS:
   - NEVER ask two things in one card.
   - NEVER write paragraphs or essays on the back.
3. TASK:
   {count_instruction}
   Extract the high-yield facts and split each into its own micro-card.
4. Plain clean text only, strictly in English.

FORMAT (JSON only):
{{
    "cards": [
        {{
            "front": "Short razor-sharp question?",
            "back": "Ultra-concise single target answer.",
            "tags": ["Tutor_Expansion"]
        }}
    ]
}}
"""
    try:
        texto_bruto = generate_text(prompt, load_ai_settings().flashcard_model, response_json=True)
        return parse_flashcards_response(texto_bruto)
    except Exception as error:
        raise FlashcardGenerationError("Não foi possível criar flashcards a partir da explicação do tutor.") from error