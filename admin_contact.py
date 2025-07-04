# admin_contact.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from config import GROUP_ID, SUPPORT_USERNAME
from db import bot

contact_router = Router()

@contact_router.message(F.text == "📞 Contact Support")
async def contact_admin(m: Message):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton("💬 Chat with Support", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")]
])
await m.answer(
    "📞 **Need help with something?**\n\n"
    "👨‍💻 Tap the button below to connect with our friendly support team 👇",
    parse_mode="Markdown",
    reply_markup=keyboard
)

