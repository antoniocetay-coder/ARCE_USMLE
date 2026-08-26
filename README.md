# ARC-e USMLE — NiceGUI + Gemini

Plataforma local de estudo USMLE com questões, flashcards, FSRS, BKT e analytics. A apresentação é exclusivamente **NiceGUI** — Streamlit não é utilizado.

## Requisitos

- Python 3.11+
- SQLite incluído no Python
- Chave Gemini opcional para geração de questões, flashcards e tutor

## Instalação

```bash
python -m venv .venv
# Git Bash
source .venv/Scripts/activate
python -m pip install -r requirements.txt pytest ruff
cp .env.example .env
```

No PowerShell, ative com `.venv\Scripts\Activate.ps1`.

## Executar

```bash
python main.py
```

Abra a URL exibida, em geral `http://127.0.0.1:8080`.

## Configuração Gemini

O aplicativo inicia sem chave. Recursos de IA ficam indisponíveis, mas revisão, histórico e analytics permanecem acessíveis.

Prioridade da chave:

1. Configurações do aplicativo, armazenada localmente no SQLite;
2. `GEMINI_API_KEY` no arquivo `.env`.

Os modelos de questões e flashcards são configuráveis pela página **Configurações**. O cliente Gemini reutiliza a instância por chave, usa o SDK `google-genai` via `models.generate_content`, solicita JSON estruturado quando necessário e converte erros de rede, chave, modelo e rate limit em mensagens seguras para a UI.

## Sessão de estudo

- **Encerrar sessão** está disponível durante estudo, pede confirmação e não marca itens pendentes como errados.
- Flashcards aprovados durante uma questão são persistidos e adicionados ao final da mesma fila.
- `Again` retorna o mesmo flashcard ao final até três vezes; `Hard`, uma vez; `Good` e `Easy` não retornam.
- A repetição na sessão é adicional ao agendamento FSRS: ela não cria outro registro de flashcard.

## Estrutura

```text
core/
├── ai/            cliente Gemini, geradores e validação
├── algorithms/    BKT, FSRS, scheduler e analytics puros
├── models/        dataclasses de domínio e fila
├── repositories/  SQLite, schema e consultas
└── services/      casos de uso de estudo, questões e flashcards
pages/             apenas apresentação NiceGUI e callbacks
tests/             pytest
```

## Persistência e migração

O banco existente nunca é recriado. Na inicialização, `database.init_db()` mantém compatibilidade histórica e `ApplicationRepository.initialize()` aplica somente DDL aditivo:

- `schema_migrations` registra a versão aplicada;
- `generated_batches` registra `request_id` e impede que o mesmo lote de questões seja salvo duas vezes;
- as tabelas existentes de questões, flashcards e SRS são preservadas.

Há backup diário antes da operação normal quando um banco já existe.

## Verificação

```bash
python -m pytest -q
ruff check .
```

A suíte cobre validação estrutural, fila de sessão, encerramento, repetição intrassessão, atomicidade e idempotência de lotes, além dos testes originais de configuração e páginas.
