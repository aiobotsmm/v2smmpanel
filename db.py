import os
import sqlite3
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# --- Load Environment Variables ---
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")

# --- Setup Bot ---
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

# --- Dispatcher with in-memory FSM storage ---
dp = Dispatcher(storage=MemoryStorage())

# --- SQLite Database Connection ---
conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cur = conn.cursor()

# --- Initialize Required Tables ---
def initialize_database():
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        phone TEXT,
        balance REAL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        txn_id TEXT UNIQUE,
        status TEXT DEFAULT 'pending'
    );

    CREATE TABLE IF NOT EXISTS complaint_tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER,
    txn_id TEXT,
    amount REAL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        order_id TEXT,
        service_name TEXT,
        link TEXT,
        quantity INTEGER,
        price REAL,
        status TEXT
    );

    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    );
    """)
    conn.commit()

def get_admin_ids():
    try:
        cur.execute("SELECT user_id FROM admins")
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"DB error in get_admin_ids(): {e}")
        return []

