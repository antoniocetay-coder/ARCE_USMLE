import json
from pydantic import BaseModel, Field

from ai.client import generate_text

class MnemonicItem(BaseModel):
    initial: str = Field(description="A letra inicial ou silaba que representa este item no mnemônico.")
    concept: str = Field(description="O conceito médico ou palavra que está sendo lembrada.")
    explanation: str = Field(description="Uma breve explicação do conceito médico no contexto da doença.")
    visual_cue: str = Field(description="Um emoji ou ícone Unicode que represente semanticamente este conceito.")

class MnemonicStructure(BaseModel):
    anchor: str = Field(description="O conceito âncora do mnemônico (ex: o nome da doença, ou sintoma principal, que serve de gatilho mental).")
    bizarre_association: str = Field(description="Uma estória ou associação mental altamente bizarra, inusitada ou absurda que ajude a reter a âncora e os itens. Use o Efeito Von Restorff (isolar e exagerar o inusitado).")
    items: list[MnemonicItem] = Field(description="Lista de itens do mnemônico. Para controlar a carga cognitiva (Chunking), o máximo absoluto de itens é 6. Tente limitar entre 4 e 6 itens principais.", max_items=6)

def generate_advanced_mnemonic(topic: str, context_notes: str = "") -> str:
    """
    Gera um mnemônico seguindo regras estritas de retenção.
    Retorna uma string JSON validada pelo schema MnemonicStructure.
    """
    prompt = f"""Você é um especialista em neurociência da aprendizagem e um educador médico experiente.
    Seu objetivo é criar um mnemônico poderoso e altamente memorável para o seguinte tópico médico:
    TÓPICO: {topic}
    NOTAS ADICIONAIS: {context_notes}

    O mnemônico DEVE seguir as seguintes regras de retenção:
    1. Dual-Coding: Cada item do mnemônico deve vir acompanhado de um ícone/emoji representativo (visual_cue).
    2. Conceito Âncora (Anchor Concept): O mnemônico não pode ficar flutuando. Ele deve ser logicamente e forçadamente amarrado a um conceito âncora relacionado à doença ou sintoma.
    3. Efeito Von Restorff: Crie uma historinha, cena, ou imagem mental BIZARRA, exagerada ou chocante envolvendo o tema, para ancorar a memória permanentemente.
    4. Carga Cognitiva (Chunking): O mnemônico não pode ter mais do que 6 letras/itens para evitar sobrecarga. Mantenha os 4 a 6 pontos clínicos de MAIOR rendimento para USMLE.

    Você DEVE retornar EXCLUSIVAMENTE um objeto JSON válido seguindo este JSON Schema estrito:
    {json.dumps(MnemonicStructure.model_json_schema(), ensure_ascii=False, indent=2)}
    
    Responda APENAS com o JSON. Nenhuma palavra a mais.
    """
    
    from ai.settings import load_ai_settings
    settings = load_ai_settings()
    
    response_text = generate_text(
        prompt=prompt,
        model=settings.flashcard_model,
        settings=settings,
        response_json=True
    )
    
    try:
        # Validate through Pydantic
        validated = MnemonicStructure.model_validate_json(response_text)
        return validated.model_dump_json()
    except Exception as e:
        # If it fails to parse cleanly, just return raw JSON if possible, but raise if totally broken
        raise ValueError(f"Failed to generate valid mnemonic JSON: {str(e)}")
