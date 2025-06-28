import sqlite3
import io
import qrcode
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from states import AddBalance
from keyboards import upi_keyboard, main_menu
from config import UPI_ID, ADMIN_ID
from db import bot, cur, conn

router = Router()
GROUP_ID = -1002897201960  # Or import from config

# --- Cancel Handler ---
@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    if await state.get_state() is None:
        return await message.answer("⚠️ Nothing to cancel.")
    await state.clear()
    await message.answer("❌ Operation cancelled.", reply_markup=main_menu())

# --- Notify Group ---
async def notify_group_payment(user_id: int, amount: float, reason: str = "Balance Update"):
    try:
        user = cur.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
        name = user[0] if user else "Unknown"

        msg = (
            f"💸 *{reason}*\n"
            f"👤 User: `{user_id}` ({name})\n"
            f"💰 Amount: ₹{amount:.2f}"
        )
        await bot.send_message(GROUP_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"❗ Group notify failed: {e}")

# --- Show Wallet Balance ---
@router.message(F.text == "💰 My Wallet")
async def show_wallet(m: Message):
    user = cur.execute("SELECT balance FROM users WHERE user_id=?", (m.from_user.id,)).fetchone()
    bal = user[0] if user else 0.0
    await m.answer(f"💵 Current Balance: ₹{bal:.2f}")

# --- Prompt Amount to Add ---
@router.message(F.text == "💰 Add Balance")
async def prompt_amount(m: Message, state: FSMContext):
    bonus_msg = (
        "🎁 *Recharge Bonus Offers:*\n"
        "• ₹500 — _Get 2% Bonus_\n"
        "• ₹1000 — _Get 3% Bonus_\n"
        "• ₹2000+ — _Get 6% Bonus_\n\n"
        "💡 Bonus is applied automatically when your payment is approved.\n"
        "🔙 Use /cancel anytime to stop."
    )
    await m.answer(bonus_msg, parse_mode="Markdown")
    await m.answer("💳 Enter the amount to add:")
    await state.set_state(AddBalance.amount)

# --- Process Entered Amount ---
@router.message(AddBalance.amount)
async def process_amount(m: Message, state: FSMContext):
    try:
        amt = round(float(m.text.strip()), 2)
        if amt <= 0:
            raise ValueError
    except ValueError:
        return await m.answer("❌ Invalid amount. Enter a number greater than 0.")

    await state.update_data(amount=amt)
    qr = f"upi://pay?pa={UPI_ID}&pn=SMMBot&am={amt}&cu=INR"
    img = qrcode.make(qr)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    await m.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="qr.png"),
        caption=f"📲 Scan & pay ₹{amt}, then click below.",
        reply_markup=upi_keyboard()
    )
    await state.set_state(AddBalance.txn_id)

# --- "I Paid" Callback ---
@router.callback_query(F.data == "paid_done")
async def ask_txnid(c: CallbackQuery, state: FSMContext):
    await c.message.answer("📥 Enter your UPI Transaction ID:")
    await c.answer()

# --- Save TXN ID ---
@router.message(AddBalance.txn_id)
async def save_txnid(m: Message, state: FSMContext):
    d = await state.get_data()
    amount = d["amount"]
    txn_id = m.text.strip()

    try:
        cur.execute(
            "INSERT INTO payments(user_id, amount, txn_id) VALUES (?, ?, ?)",
            (m.from_user.id, amount, txn_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return await m.answer("❗ This transaction ID is already used.")

    approve_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Approve", callback_data=f"ap_{m.from_user.id}_{amount}_{txn_id}")],
        [InlineKeyboardButton(text="❌ Decline", callback_data=f"de_{m.from_user.id}_{amount}_{txn_id}")]
    ])

    await m.answer("✅ Submitted for approval. You’ll be notified once processed.")
    await bot.send_message(
        ADMIN_ID,
        f"🧾 *New Payment Request*\n"
        f"👤 User ID: `{m.from_user.id}`\n"
        f"💸 Amount: ₹{amount}\n"
        f"🧾 Txn ID: `{txn_id}`",
        reply_markup=approve_btn,
        parse_mode="Markdown"
    )
    await state.clear()

# --- Approve Payment ---
@router.callback_query(F.data.startswith("ap_"))
async def approve_payment(callback: CallbackQuery):
    try:
        _, uid, amt, txn = callback.data.split("_", 3)
        user_id = int(uid)
        amount = float(amt)

        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        cur.execute("UPDATE payments SET status = 'approved' WHERE txn_id = ?", (txn,))
        conn.commit()

        await callback.message.edit_text("✅ Payment Approved!")
        await bot.send_message(user_id, f"✅ ₹{amount:.2f} has been added to your wallet.")
        await notify_group_payment(user_id, amount, "✅ Payment Approved")

    except Exception as e:
        await callback.answer("⚠️ Approval failed.", show_alert=True)
        print("❌ Error approving payment:", e)

# --- Decline Payment ---
@router.callback_query(F.data.startswith("de_"))
async def decline_payment(callback: CallbackQuery):
    try:
        _, uid, amt, txn = callback.data.split("_", 3)
        user_id = int(uid)
        amount = float(amt)

        cur.execute("UPDATE payments SET status = 'declined' WHERE txn_id = ?", (txn,))
        conn.commit()

        await callback.message.edit_text("❌ Payment Declined.")
        await bot.send_message(user_id, f"❌ Your payment of ₹{amount:.2f} was declined.")

    except Exception as e:
        await callback.answer("⚠️ Decline failed.", show_alert=True)
        print("❌ Error declining payment:", e)
