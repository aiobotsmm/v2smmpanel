from aiogram import Router, F
from aiogram.types import Message
from keyboards import admin_panel_keyboard
from utils.admin_utils import is_admin  # import your is_admin() helper

router = Router()

@router.message(F.text == "👮 Admin Panel")
async def show_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ You are not authorized.")

    await message.answer("🔐 *Admin Panel Accessed*", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
