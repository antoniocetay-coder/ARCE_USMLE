import json
import sqlite3

conn = sqlite3.connect('usmle_data.db')
c = conn.cursor()
c.execute("SELECT question_json FROM questions ORDER BY id DESC LIMIT 1")
row = c.fetchone()
if row:
    print(json.dumps(json.loads(row[0]), indent=2))
