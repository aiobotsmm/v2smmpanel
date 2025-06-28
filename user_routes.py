from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from states import Register
from keyboards import main_menu
from db import cur, conn

router = Router()

# --- /start Command ---
@router.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext):
    try:
        row = cur.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,)).fetchone()
        if row:
            balance = row[0] or 0
            await m.answer(
                f"👋 Welcome back!\n💰 Balance: ₹{balance:.2f}",
                reply_markup=main_menu(balance)
            )
            await state.clear()
        else:
            await m.answer("👋 Welcome! Please enter your full name to register:")
            await state.set_state(Register.name)

    except Exception as e:
        await m.answer("⚠️ An error occurred. Please try again later.")
        print(f"Error in /start: {e}")

# --- Collect Name ---
@router.message(Register.name)
async def reg_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await m.answer("📞 Please enter your phone number:")
    await state.set_state(Register.phone)

# --- Collect Phone ---
@router.message(Register.phone)
async def reg_phone(m: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("name")
    phone = m.text.strip()

    try:
        cur.execute(
            "INSERT OR IGNORE INTO users(user_id, name, phone) VALUES (?, ?, ?)",
            (m.from_user.id, name, phone)
        )
        conn.commit()

        row = cur.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,)).fetchone()
        balance = row[0] if row else 0

        await m.answer(
            "✅ Registration complete!\n\n"
            "💡 Tip: At any point, you can use /cancel to stop an action.",
            reply_markup=main_menu(balance)
        )
        await state.clear()

    except Exception as e:
        await m.answer("⚠️ Registration failed. Please try again.")
        print(f"Error during registration: {e}")
        await state.clear()
