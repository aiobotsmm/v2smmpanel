from aiogram import Router, F
from aiogram.types import Message
from keyboards import admin_panel_keyboard
from admin_utils import is_admin  # import your is_admin() helper

router = Router()

@router.message(F.text == "👮 Admin Panel")
async def show_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ You are not authorized.")

    await message.answer("🔐 *Admin Panel Accessed*", parse_mode="Markdown", reply_markup=admin_panel_keyboard())
#add or remove admin id
from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

@router.callback_query(F.data == "add_admin")
async def handle_add_admin(callback: CallbackQuery):
    await callback.answer("🛠 Add Admin clicked!")
    await callback.message.answer("🆔 Please send the User ID to make admin:")

@router.callback_query(F.data == "remove_admin")
async def handle_remove_admin(callback: CallbackQuery):
    await callback.answer("🛠 Remove Admin clicked!")
    await callback.message.answer("🆔 Please send the User ID to remove from admin:")

