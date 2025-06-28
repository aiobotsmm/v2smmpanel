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
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from states import AdminAction
from db import cur, conn
from aiogram.filters import Command

router = Router()

@router.callback_query(F.data == "add_admin")
async def handle_add_admin(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("🆔 Send the user ID to add as admin:")
    await state.set_state(AdminAction.adding_admin)

@router.callback_query(F.data == "remove_admin")
async def handle_remove_admin(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("🆔 Send the user ID to remove from admin:")
    await state.set_state(AdminAction.removing_admin)

# 💾 Handle entered admin ID for adding
@router.message(AdminAction.adding_admin)
async def process_add_admin_id(message: Message, state: FSMContext):
    try:
        new_admin_id = int(message.text.strip())
        cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES (?)", (new_admin_id,))
        conn.commit()
        await message.answer(f"✅ User `{new_admin_id}` added as admin.", parse_mode="Markdown")
    except Exception as e:
        await message.answer("❌ Failed to add admin.")
        print(e)
    await state.clear()

# 💾 Handle entered admin ID for removing
@router.message(AdminAction.removing_admin)
async def process_remove_admin_id(message: Message, state: FSMContext):
    try:
        remove_id = int(message.text.strip())
        cur.execute("DELETE FROM admins WHERE user_id = ?", (remove_id,))
        conn.commit()
        await message.answer(f"❌ User `{remove_id}` removed from admin.", parse_mode="Markdown")
    except Exception as e:
        await message.answer("❌ Failed to remove admin.")
        print(e)
    await state.clear()


