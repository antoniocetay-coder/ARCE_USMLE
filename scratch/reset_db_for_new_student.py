import shutil
import sqlite3
import sys
import io
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "usmle_data.db"
BACKUPS_DIR = PROJECT_ROOT / "backups"


def reset_database_for_new_student():
    if not DB_PATH.exists():
        print(f"Database {DB_PATH} not found.")
        return

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"pre_reset_backup_{timestamp}.db"

    print(f"📦 Criando backup de segurança em: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    student_tables = [
        "questions",
        "flashcards",
        "srs_state",
        "tag_stats",
        "erros_por_sistema",
        "confusions",
        "tag_cooldown",
        "generated_batches",
        "isomorphic_vignettes",
        "mnemonics",
    ]

    print("\n🧹 Limpando dados de atividade do aluno (Clean Slate)...")
    for tbl in student_tables:
        try:
            cursor.execute(f"DELETE FROM {tbl}")
            print(f"   ✓ Tabela '{tbl}' resetada (0 registros).")
        except sqlite3.OperationalError as e:
            print(f"   - Tabela '{tbl}' não encontrada ou já limpa ({e}).")

    # Reset SQLite autoincrement sequences for cleared tables
    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('questions', 'flashcards', 'isomorphic_vignettes')")
    except Exception:
        pass

    conn.commit()

    # Preserved Knowledge Vault & Settings check
    nodes_count = cursor.execute("SELECT COUNT(*) FROM knowledge_nodes").fetchone()[0]
    edges_count = cursor.execute("SELECT COUNT(*) FROM ontology_edges").fetchone()[0]
    ai_config = cursor.execute("SELECT api_key, question_model, flashcard_model FROM ai_configuration WHERE id=1").fetchone()

    conn.execute("VACUUM")
    conn.execute("ANALYZE")
    conn.close()

    print("\n" + "=" * 60)
    print("✨ BANCO DE DADOS RESETADO COM SUCESSO!")
    print("=" * 60)
    print(f"• Aluno Novo: 0 questões respondidas, 0 flashcards, 0 confusões.")
    print(f"• Obsidian Knowledge Vault Preservado: {nodes_count:,} nós médicos | {edges_count:,} arestas ontológicas.")
    print(f"• Configurações de IA Preservadas: API Key e modelos mantidos.")
    print(f"• Backup Seguro: {backup_path.name}")
    print("=" * 60)


if __name__ == "__main__":
    reset_database_for_new_student()
