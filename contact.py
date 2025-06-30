import re
import os
import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from db import get_admin_ids, init as init_db  # ✅ Use your db.py

# === Load Contact Bot Token ===
load_dotenv()
CONTACT_BOT_TOKEN = os.getenv("CONTACT_BOT_TOKEN")  # Add this in your .env file

# === Initialize DB (admins table etc.) ===
init_db()

# === Bot + Dispatcher ===
bot = Bot(
    token=CONTACT_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# === Handle user messages ===
@router.message(F.text & ~F.from_user.id.in_(get_admin_ids()))
async def forward_user_msg(message: Message):
    user = message.from_user
    user_info = f"📩 Message from @{user.username or user.first_name}\n🆔 ID: <code>{user.id}</code>"
    full_msg = f"{user_info}\n\n{message.html_text}"

    for admin_id in get_admin_ids():
        try:
            await bot.send_message(admin_id, full_msg)
        except Exception as e:
            print(f"Failed to send message to admin {admin_id}: {e}")

    await message.answer("✅ Your message has been sent to the support team.")

# === Handle admin replies ===
@router.message(F.reply_to_message & F.from_user.id.in_(get_admin_ids()))
async def handle_admin_reply(message: Message):
    original = message.reply_to_message.text
    match = re.search(r"ID:\s?<code>(\d+)</code>", original)
    if not match:
        return await message.answer("❌ User ID not found in original message.")

    user_id = int(match.group(1))
    try:
        await bot.send_message(user_id, f"🛠️ Support: {message.html_text}")
        await message.answer("✅ Reply sent to user.")
    except Exception as e:
        await message.answer(f"❌ Failed to send message: {e}")

# === Run contact bot ===
async def main():
    dp.include_router(router)
    print("📞 Contact bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
