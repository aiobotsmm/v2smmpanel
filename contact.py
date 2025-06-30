import re
import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from db import initialize_database

# === Hardcoded Config ===
CONTACT_BOT_TOKEN = "8178918373:AAGoV0MpOp-TaMbnS4YhyFJvK8yhOB44TQk"
ADMIN_IDS = [5274097505, 6364118939]
SUPPORT_GROUP_ID = -1002897201960  # ← your group ID here

# === Init DB ===
initialize_database()

# === Bot & Dispatcher ===
bot = Bot(token=CONTACT_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# === USER → GROUP ===
@router.message(F.text & ~F.from_user.id.in_(ADMIN_IDS))
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
        await message.answer("❌ Failed to send your message. Please try again later.")

# === ADMIN REPLY → USER ===
@router.message(F.reply_to_message & F.chat.id == SUPPORT_GROUP_ID)
async def handle_admin_reply(message: Message):
    original = message.reply_to_message
    original_text = original.text or ""

    print("DEBUG >>> Original replied message:\n", original_text)

    # Updated regex to match ID without <code> tags
    match = re.search(r"ID[:：]?\s*(\d+)", original_text)
    if not match:
        return await message.reply("❌ User ID not found in the original message.\nMake sure you replied to the correct bot message.")

    user_id = int(match.group(1))

    try:
        await bot.send_message(chat_id=user_id, text=f"🛠️ Admin:\n\n{message.html_text}")
        await message.reply("✅ Message sent to user.")
    except Exception as e:
        await message.reply(f"❌ Failed to send message: {e}")



# === MAIN ===
async def main():
    dp.include_router(router)
    print("📞 Contact bot with GROUP support is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
