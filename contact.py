import asyncio
import re
import sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

# === DB Setup ===
DB_PATH = "db.py"  # Update path if needed

def get_admin_ids():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM admins")  # Or use 'id' if that's your column
        admin_ids = [row[0] for row in cur.fetchall()]
        conn.close()
        return admin_ids
    except Exception as e:
        print(f"DB error: {e}")
        return []

# === Bot Setup ===
CONTACT_BOT_TOKEN = "8178918373:AAGoV0MpOp-TaMbnS4YhyFJvK8yhOB44TQk"
bot = Bot(token=CONTACT_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# === User sends message (forward to admins from DB) ===
@router.message(F.text)
async def handle_user_message(message: Message):
    user = message.from_user
    admin_ids = get_admin_ids()

    # If message is from admin, allow replies only
    if user.id in admin_ids and message.reply_to_message:
        return await handle_admin_reply(message)

    if user.id in admin_ids:
        return  # Ignore new messages from admins that are not replies

    user_info = f"📩 Message from @{user.username or user.first_name}\n🆔 ID: <code>{user.id}</code>"
    full_msg = f"{user_info}\n\n{message.text}"

    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=full_msg)
        except Exception as e:
            print(f"❌ Failed to forward to admin {admin_id}: {e}")

    await message.answer("✅ Your message has been sent to the support team.")

# === Admin replies (send to user) ===
async def handle_admin_reply(message: Message):
    original = message.reply_to_message.text
    match = re.search(r"ID:\s?<code>(\d+)</code>", original)

    if not match:
        return await message.answer("❌ User ID not found in original message.")

    user_id = int(match.group(1))
    try:
        await bot.send_message(chat_id=user_id, text=f"🛠️ Support: {message.text}")
        await message.answer("✅ Reply sent to user.")
    except Exception as e:
        await message.answer(f"❌ Failed to send message: {e}")
