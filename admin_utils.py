from config import ADMIN_IDS
from db import cur

def is_admin(user_id: int) -> bool:
    row = cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
    return bool(row)
    return user_id in ADMIN_IDS
