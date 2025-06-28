from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from config import GROUP_ID
from db import bot

group_router = Router()

# ✅ Print group ID when added (for setup/debug only)
@group_router.message(F.chat.type.in_({"group", "supergroup"}))
async def show_group_id(m: Message):
    print(f"[Group ID] {m.chat.title} — ID: {m.chat.id}")
    await m.answer(f"ℹ️ This group's chat ID is: `{m.chat.id}`", parse_mode="Markdown")

# ✅ /testgroup command — tests if bot can send to GROUP_ID
@group_router.message(Command("testgroup"))
async def test_group_send(m: Message):
    try:
        await bot.send_message(GROUP_ID, "✅ Bot is able to send messages to this group!")
        await m.answer("✅ Test message sent to the group.")
    except Exception as e:
        await m.answer("❌ Failed to send to group. Check if:\n• Bot is in the group\n• Bot is admin\n• GROUP_ID is correct")
        print(f"[TestGroup Error] {e}")
