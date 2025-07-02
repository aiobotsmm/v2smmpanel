import sqlite3

# Connect to your SQLite DB file
conn = sqlite3.connect("database.db")  # replace with your DB file name if different
cur = conn.cursor()

# Try to add the column
try:
    cur.execute("ALTER TABLE complaint_tokens ADD COLUMN total_price REAL;")
    print("✅ Column 'total_price' added successfully.")
except sqlite3.OperationalError as e:
    print("⚠️", e)

conn.commit()
conn.close()
