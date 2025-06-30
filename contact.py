import re
import os
import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from db import initialize_database

# === Load env ===
load_dotenv()
CONTACT_BOT_TOKEN = os.getenv("CONTACT_BOT_TOKEN")
SUPPORT_GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID"))  # e.g., -1001234567890

# === Init DB ===
initialize_database()

# === Bot & Dispatcher ===
bot = Bot(
    token=CONTACT_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# === USER to SUPPORT GROUP ===
@router.message(F.text)
async def handle_user_msg(message: Message):
    user = message.from_user
    msg = (
        f"📩 Message from @{user.username or user.full_name}\n"
        f"🆔 ID:<code>{user.id}</code>\n\n"
        f"{message.html_text}"
    )
    try:
        await bot.send_message(SUPPORT_GROUP_ID, msg)
        await message.answer("✅ Your message has been sent to the support team.")
    except Exception as e:
        print("Group send error:", e)
        await message.answer("❌ Failed to send message. Please try later.")

# === ADMIN REPLY (from group) to USER ===
@router.message(F.reply_to_message & F.chat.id == SUPPORT_GROUP_ID)
async def handle_admin_reply(message: Message):
    original = message.reply_to_message.text
    match = re.search(r"ID:<code>(\d+)</code>", original)
    if not match:
        return await message.answer("❌ User ID not found in the original message.")

    user_id = int(match.group(1))
    try:
        await bot.send_message(user_id, f"🛠️ Support: {message.html_text}")
        await message.answer("✅ Reply sent to user.")
    except Exception as e:
        await message.answer(f"❌ Failed to message user: {e}")

# === MAIN ===
async def main():
    dp.include_router(router)
    print("📞 Contact bot with GROUP support is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
