import sqlite3

from database import get_conn, init_db


def reset_user_data():
    conn = get_conn()
    tables_to_clear = [
        "questions",
        "flashcards",
        "srs_state",
        "tag_stats",
        "erros_por_sistema",
        "tag_cooldown",
        "confusions",
        "high_yield_pearls",
        "mnemonics"
    ]
    
    with conn:
        for table in tables_to_clear:
            conn.execute(f"DELETE FROM {table}")
            
    print("User data reset completed successfully. Knowledge base preserved.")

if __name__ == "__main__":
    reset_user_data()
