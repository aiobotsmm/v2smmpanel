import asyncio
import re
import os
from aiogram import Router
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.router import Router
from dotenv import load_dotenv

# === Load Bot Token and Admins ===
load_dotenv()
CONTACT_BOT_TOKEN = os.getenv("CONTACT_BOT_TOKEN")  # Add this in your .env file
ADMINS = [123456789, 987654321]  # Replace with actual admin Telegram IDs

# === Bot and Dispatcher Setup ===
bot = Bot(token=CONTACT_BOT_TOKEN, parse_mode=ParseMode.HTML)
router = Router()

# === Handle user message (forward to admins) ===
@router.message(F.text & ~F.from_user.id.in_(ADMINS))
async def handle_user_message(message: Message):
    user = message.from_user
    user_info = f"📩 Message from @{user.username or user.first_name}\n🆔 ID: <code>{user.id}</code>"
    full_msg = f"{user_info}\n\n{message.text}"

    # Forward to all admins
    for admin_id in ADMINS:
        try:
            await bot.send_message(chat_id=admin_id, text=full_msg)
        except Exception as e:
            print(f"Error sending to admin {admin_id}: {e}")

    await message.answer("✅ Your message has been sent to the support team.")

# === Admin replies (goes back to user) ===
@router.message(F.reply_to_message & F.from_user.id.in_(ADMINS))
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
