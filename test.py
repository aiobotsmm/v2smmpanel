import sqlite3

conn = sqlite3.connect("db.sqlite3")
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    txn_id TEXT UNIQUE,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
conn.close()

print("✅ DB and table created successfully.")
