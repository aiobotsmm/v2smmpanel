# admin_contact.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from config import GROUP_ID, SUPPORT_USERNAME
from db import bot

contact_router = Router()

@contact_router.message(F.text == "📞 Contact Admin")
async def contact_admin(m: Message):
    await m.answer(f"📩 Contact support: @{SUPPORT_USERNAME}", parse_mode=None)
