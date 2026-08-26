import json
import logging
import uuid

from pydantic import ValidationError

from ai.client import generate_text
from ai.settings import load_ai_settings
from core.ai.legacy_validation import limpar_json
from core.ai.schema import QuestionBatch
from core.exceptions import QuestionGenerationError, TutorGenerationError
from taxonomy import TAXONOMIA_COMPLETA

logger = logging.getLogger(__name__)


QUESTION_BATCH_PROMPT_VERSION = "v2"
MAX_BATCH_RETRIES = 2


# ==============================================================================
# AI ENGINE - BATCH GENERATOR
# ==============================================================================
def gerar_prompt_lote(sistema, difficulty, cognitive_order, tags_alvo, num_questoes):
    tags_text = ", ".join(tags_alvo) if tags_alvo else "None"
    
    # RAG Context Retrieval from Obsidian Knowledge Vault (8.044 notes, 54 ontologies)
    rag_context = ""
    try:
        from core.ai.rag_service import RAGService
        query_terms = list(tags_alvo) if tags_alvo else [sistema]
        rag_context = RAGService().search_knowledge_context(query_terms, limit=5)
    except Exception as e:
        logger.warning("RAG context retrieval skipped: %s", e)

    rag_instruction = ""
    if rag_context:
        rag_instruction = f"""
OFFICIAL OBSIDIAN KNOWLEDGE BASE CONTEXT (GROUND TRUTH):
Use the following official medical facts and node fragments from the Obsidian Vault to guide question creation, distractor rationale, and explanations:

{rag_context}
"""

    confounder_instruction = ""
    if tags_alvo:
        from core.services.analytics_service import AnalyticsService
        confounders = []
        for tag in tags_alvo:
            confounders.extend(AnalyticsService().get_top_confounders(tag))
        
        if confounders:
            confounders = list(set(confounders))
            confounder_instruction = f"""
STUDENT'S KNOWN CONFUSIONS:
The student frequently confuses the correct answer with these concepts: {', '.join(confounders)}
If applicable, YOU MUST include at least one of these concepts as a highly plausible DISTRACTOR.
"""

    import json as _json
    tax_json = _json.dumps(TAXONOMIA_COMPLETA, ensure_ascii=False, indent=2)

    return f"""
You are an elite NBME-style USMLE question writer.
QUESTION_BATCH_PROMPT_VERSION: {QUESTION_BATCH_PROMPT_VERSION}
Generate EXACTLY {num_questoes} high-quality USMLE clinical vignettes in this SINGLE JSON response.
Do not truncate the list. Every vignette and tested concept must be distinct. Distribute concepts across TARGET CONCEPTS where possible.

PRIMARY SYSTEM: {sistema}
DIFFICULTY: {difficulty}
TARGET CONCEPTS: {tags_text}
COGNITIVE DEPTH REQUIRED: {cognitive_order}
{rag_instruction}
{confounder_instruction}

CRITICAL RULES:
1. You MUST write exactly ONE question for each of the TARGET CONCEPTS listed above to ensure no repetition within this batch.
2. You MUST strictly adhere to the COGNITIVE DEPTH REQUIRED:
   - If "1st Order": Ask "What is the most likely diagnosis?".
   - If "2nd Order": Give away the diagnosis subtly in the vignette. Ask about the underlying mechanism, pathophysiology, or best next step.
   - If "3rd Order": Give away the diagnosis. Ask about the mechanism of action of the drug used to treat the main complication, or the embryological origin of the affected tissue.
3. LANGUAGE RULE: All vignette text, options, and explanations MUST be strictly in English.

{confounder_instruction}

STRICT TAXONOMY RULE:
You MUST classify each question using exact tags from the JSON below. Do NOT invent tags.

ALLOWED TAXONOMY:
{tax_json}

STRICT DISTRACTOR TAGGING RULE:
For every single option in "options" (A, B, C, D, E), you MUST associate it with its specific medical concept/tag from the ALLOWED TAXONOMY above.
- The correct option must point to the correct concept tested.
- Each distractor (incorrect option) must point to the specific decoy/distractor concept it represents.

RETURN FORMAT:
You MUST return a valid JSON object containing an array called "questions". Do not use markdown blocks outside the JSON.

{{
  "questions": [
    {{
        "vignette": "A 45-year-old man presents with...",
        "options": ["A) ...", "B) ...", "C) ...", "D) ...", "E) ..."],
        "correct": "A",
        "explanations": {{
            "A": "...", "B": "...", "C": "...", "D": "...", "E": "..."
        }},
        "educational_objective": "...",
        "content_tags": ["Tag 1", "Tag 2"],
        "distractor_tags": {{
            "A": "Exact Tag for Option A",
            "B": "Exact Tag for Option B",
            "C": "Exact Tag for Option C",
            "D": "Exact Tag for Option D",
            "E": "Exact Tag for Option E"
        }}
    }}
  ]
}}
"""

def gerar_lote_questoes(sistema, difficulty, cognitive_order, tags_alvo, num_questoes):
    batch_id = str(uuid.uuid4())
    logger.info("Generating Gemini question batch batch_id=%s requested=%s prompt_version=%s", batch_id, num_questoes, QUESTION_BATCH_PROMPT_VERSION)

    for attempt in range(MAX_BATCH_RETRIES):
        prompt = gerar_prompt_lote(sistema, difficulty, cognitive_order, tags_alvo, num_questoes)
        try:
            texto_bruto = generate_text(prompt, load_ai_settings().question_model, response_json=True)
            texto = limpar_json(texto_bruto)

            if not texto:
                logger.warning("Gemini returned an empty question payload. Raw output was: %s", texto_bruto)
                if attempt < MAX_BATCH_RETRIES - 1:
                    continue
                return []

            dados = json.loads(texto)
            batch = QuestionBatch.model_validate(dados)
            questoes_validas = []

            for q in batch.questions:
                q_dict = q.model_dump()
                q_dict["correct"] = q_dict["correct"].strip().upper()[0]
                questoes_validas.append(q_dict)

            logger.info(
                "Gemini question batch completed batch_id=%s requested=%s returned=%s valid=%s",
                batch_id, num_questoes, len(batch.questions), len(questoes_validas)
            )
            return questoes_validas

        except ValidationError as ve:
            logger.warning(f"Pydantic validation failed on attempt {attempt+1}: {ve}")
            if attempt == MAX_BATCH_RETRIES - 1:
                logger.error("Max retries reached for Pydantic validation. Failing.")
                return []
            continue

        except Exception as error:
            if attempt == MAX_BATCH_RETRIES - 1:
                raise QuestionGenerationError("Não foi possível gerar as questões com o Gemini.") from error
            continue

    return []

def gerar_questao(sistema, difficulty, tags_alvo=None):
    res = gerar_lote_questoes(sistema, difficulty, "2nd Order (Pathophysiology/Next Step in Management)", tags_alvo, 1)
    return res[0] if res else None

def explicar_duvida_tutor(contexto_material, duvida_aluno):
    prompt = f"""
You are an elite, empathetic USMLE tutor (Step 1 and Step 2 CK).
The student is currently studying the following material (Flashcard or Question):

MATERIAL CONTEXT:
{contexto_material}

STUDENT'S DOUBT:
"{duvida_aluno}"

TASK:
Provide a highly accurate, concise, and easy-to-understand explanation.
- Speak directly to the student.
- Focus STRICTLY on clarifying their doubt using the provided context.
- Use bold text for key physiological or pharmacological mechanisms.
- Keep your answer between 1 and 3 short paragraphs. DO NOT write a giant essay.
- Write STRICTLY in English.
"""
    try:
        return generate_text(prompt, load_ai_settings().flashcard_model)
    except Exception as error:
        raise TutorGenerationError("Não foi possível contatar o tutor de IA.") from error


def gerar_mnemonico_ia(contexto_material: str, estilo: str = "Dual-Coding Visual") -> str:
    prompt = f"""
You are an expert USMLE medical educator specializing in high-yield mnemonics and memory retention science for Step 1 & Step 2 CK.
Create a high-retention, medically accurate mnemonic or memory hook for the following medical concept.

MATERIAL CONTEXT:
{contexto_material}

DESIRED MNEMONIC STYLE: {estilo}

SCIENTIFIC RETENTION RULES (CRITICAL):
1. ANCHOR CONCEPT RULE: You MUST explicitly tie the disease/condition name directly into the mnemonic title/trigger so the student never experiences "Mnemonic Isolation" (forgetting which disease the mnemonic belongs to).
2. DUAL-CODING RULE: Include a vivid, bizarre, or emotionally striking VISUAL SCENE description (Sketchy-style mental image) to code the concept both visually and verbally.
3. COGNITIVE LOAD RULE: Keep acronyms short (max 4-6 key items). Do not overload working memory.
4. HIGH-YIELD PEARL: End with 1 sharp sentence explaining how this exact concept is tested on the USMLE.
5. ACTIVE RECALL CUE: Provide a quick 1-sentence self-test question at the end.

REQUIRED FORMAT (Strict Markdown):
# 🎯 Mnemonic Anchor: [Condition Name] - [Short Memorable Title]

### 🖼️ Dual-Coding Visual Scene (Mental Image)
[1-2 sentences describing a vivid, bizarre mental image connecting the condition to the core pathology/symptoms]

### 🔤 Mnemonic Breakdown
* **[Letter/Word 1]** - Explanation & USMLE fact
* **[Letter/Word 2]** - Explanation & USMLE fact
* **[Letter/Word 3]** - Explanation & USMLE fact

### 💎 High-Yield Exam Pearl
**USMLE Pearl:** [1 sentence connecting this mnemonic directly to exam questions]

### 🧠 Active Recall Test
*Recall Question:* [1 quick self-test question to verify retention]
"""
    try:
        return generate_text(prompt, load_ai_settings().flashcard_model)
    except Exception as error:
        raise TutorGenerationError("Não foi possível gerar o mnemônico.") from error



def desmistificar_distratores(question: dict) -> str:
    prompt = f"""
You are an expert USMLE Question Analyzer.
Analyze the following clinical vignette, options, correct answer, and explanations:

VIGNETTE: {question.get('vignette')}
OPTIONS: {json.dumps(question.get('options'))}
CORRECT OPTION: {question.get('correct')}
EXPLANATIONS: {json.dumps(question.get('explanations'))}

TASK:
For EVERY INCORRECT option (distractor), write a concise reverse-differential breakdown STRICTLY in English:
"Option [X] would be correct IF: [Describe the precise patient presentation, lab finding, or clinical scenario that would make option X the correct answer]."

Keep each option breakdown to 1-2 sharp sentences.
"""
    try:
        return generate_text(prompt, load_ai_settings().flashcard_model, use_cache=True)
    except Exception as error:
        raise TutorGenerationError("Não foi possível desmistificar os distratores.") from error


def extrair_perola_hy(contexto_material: str) -> str:
    prompt = f"""
You are a USMLE Step 1 High-Yield Expert.
Extract EXACTLY ONE high-yield 1-sentence "Exam Pearl" from the following material.

MATERIAL:
{contexto_material}

FORMAT:
A single punchy sentence starting with "💎 **USMLE Pearl:** [High-yield rule/association]". Write STRICTLY in English.
"""
    try:
        return generate_text(prompt, load_ai_settings().flashcard_model, use_cache=True)
    except Exception as error:
        raise TutorGenerationError("Não foi possível extrair a pérola de alto rendimento.") from error


def explicar_socratico(contexto_material: str, duvida_aluno: str) -> str:
    prompt = f"""
You are a Master Socratic USMLE Tutor.
The student is studying the following material:
{contexto_material}

Student's question/doubt: "{duvida_aluno}"

TASK:
DO NOT give the direct answer! Instead, act as a Socratic guide:
1. Briefly acknowledge their question.
2. Ask 1 or 2 targeted, guiding questions about the underlying pathophysiology or key mechanism that will help the student deduce the correct answer on their own.
Write STRICTLY in English in an encouraging, expert tone.
"""
    try:
        return generate_text(prompt, load_ai_settings().flashcard_model)
    except Exception as error:
        raise TutorGenerationError("Não foi possível contatar o tutor socrático.") from error