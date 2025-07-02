import asyncio
import secrets
import sqlite3
import os
import aiohttp

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from db import cur, conn, bot
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from dotenv import load_dotenv

# === Load .env ===
load_dotenv()
BOT_TOKEN = "5925186202:AAH64rf6SQqYSFw3pC-DrfEs0eOg-QLrU1I"
GROUP_ID = int(os.getenv("GROUP_ID"))
API_URL = os.getenv("SMM_API_URL")
API_KEY = os.getenv("SMM_API_KEY")
ADMIN_ID= 5274097505

# === Bot Init ===
from aiogram.client.default import DefaultBotProperties

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
router = Router()
dp.include_router(router)


# === FSM ===
class OrderStates(StatesGroup):
    waiting_token = State()
    browsing_services = State()
    entering_link = State()
    entering_quantity = State()
    confirm_order = State()


# === /start ===
@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_token)
    await message.answer("🔐 Please enter your 8-digit token to verify.")


# === Token Verification ===
@router.message(OrderStates.waiting_token)
async def handle_token(message: Message, state: FSMContext):
    token = message.text.strip()
    cur.execute("SELECT user_id, txn_id, amount FROM complaint_tokens WHERE token = ?", (token,))
    row = cur.fetchone()

    if not row:
        return await message.answer("❌ Invalid or expired token.")

    user_id, txn_id, amount = row

    # Save details in FSM state
    await state.update_data(
        token=token,
        user_id=user_id,
        txn_id=txn_id,
        amount=amount
    )

    # Proceed to next step
    await message.answer("✅ Token accepted. Now choose your service...")
    await state.set_state(OrderStates.browsing_services)


    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💼 My Wallet")],
            [KeyboardButton(text="🛒 New Order")]
        ],
        resize_keyboard=True
    )

    await state.set_state(OrderStates.browsing_services)

    await message.answer(
        f"✅ Token Verified!\n\n"
        f"💼 Wallet: ₹{amount}\n"
        f"🧾 TXN ID: <code>{txn_id}</code>\n\n"
        f"Choose an option below:",
        reply_markup=keyboard
    )


# === Wallet Check ===
@router.message(F.text == "💼 My Wallet")
async def show_wallet(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", "0.00")
    await message.answer(f"💼 Your current wallet balance is ₹{amount}")


# === New Order Start ===
@router.message(F.text == "🛒 New Order")
async def start_order(message: Message, state: FSMContext):
    await state.set_state(OrderStates.browsing_services)
    await show_services(message, state, page=1)


# === Show Services Paginated ===
async def show_services(message: Message, state: FSMContext, page: int):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, data={"key": API_KEY, "action": "services"}) as resp:
                if resp.status != 200:
                    return await message.answer(f"❌ API Error {resp.status}: {await resp.text()}")
                services = await resp.json()
                if not isinstance(services, list):
                    return await message.answer(f"❌ SMM API Error: {services.get('error', 'Unknown error')}")
        except Exception as e:
            return await message.answer(f"⚠️ Failed to fetch services:\n<code>{e}</code>")

    per_page = 8
    total = len(services)
    start = (page - 1) * per_page
    end = start + per_page
    current_services = services[start:end]

    if not current_services:
        return await message.answer("❌ No services found.")

    text = "📦 <b>Available Services:</b>\n\n"
    btns = []

    for svc in current_services:
        rate = round(float(svc['rate']) * 1.1, 2)
        text += f"🔹 {svc['name']} - ₹{rate}/1k\n"
        btns.append([KeyboardButton(text=svc['name'])])

    # Pagination
    if page > 1:
        btns.append([KeyboardButton(text=f"⬅️ Prev Page {page - 1}")])
    if end < total:
        btns.append([KeyboardButton(text=f"➡️ Next Page {page + 1}")])

    await state.update_data(all_services=services, current_page=page)
    await message.answer(text + "\nTap a service to view more ↓", reply_markup=ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True))


# === Pagination Navigation ===
@router.message(F.text.startswith("⬅️") | F.text.startswith("➡️"))
async def handle_pagination(message: Message, state: FSMContext):
    parts = message.text.split("Page")
    if len(parts) == 2:
        page = int(parts[1].strip())
        await show_services(message, state, page)


# === Show Single Service ===
@router.message(OrderStates.browsing_services)
async def service_detail(message: Message, state: FSMContext):
    data = await state.get_data()
    all_services = data.get("all_services", [])
    svc_name = message.text.strip()

    matched = next((s for s in all_services if s["name"].lower() == svc_name.lower()), None)
    if not matched:
        return await message.answer("❌ Service not found.")

    rate = round(float(matched['rate']) * 1.1, 2)
    desc = (
        f"📝 <b>Service Details:</b>\n\n"
        f"🔸 <b>Name:</b> {matched['name']}\n"
        f"💰 <b>Price:</b> ₹{rate}/1k\n"
        f"📉 <b>Min:</b> {matched.get('min')}, 📈 <b>Max:</b> {matched.get('max')}\n"
        f"⚡ <b>Speed:</b> {matched.get('speed')}\n"
        f"ℹ️ <b>Desc:</b> {matched.get('desc') or 'No description'}\n\n"
        f"👉 Press 'Continue' to enter link"
    )

    await state.update_data(service=matched)
    await state.set_state(OrderStates.entering_link)

    await message.answer(desc, reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Continue")], [KeyboardButton(text="⬅️ Back to Services")]],
        resize_keyboard=True
    ))


# === Back Button
@router.message(F.text == "⬅️ Back to Services")
async def go_back_to_services(message: Message, state: FSMContext):
    data = await state.get_data()
    page = data.get("current_page", 1)
    await show_services(message, state, page)


# === Ask for Link
@router.message(OrderStates.entering_link, F.text == "✅ Continue")
async def ask_link(message: Message, state: FSMContext):
    await message.answer("🔗 Please enter the link for this order:", reply_markup=ReplyKeyboardRemove())


# === Receive Link
@router.message(OrderStates.entering_link)
async def receive_link(message: Message, state: FSMContext):
    link = message.text.strip()
    await state.update_data(link=link)
    await state.set_state(OrderStates.entering_quantity)
    await message.answer("🔢 Enter the quantity you want:")


# === Quantity
@router.message(OrderStates.entering_quantity)
async def receive_quantity(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Please enter a valid number.")

    data = await state.get_data()
    service = data["service"]
    rate = round(float(service["rate"]) * 1.1, 2)
    total = (qty / 1000) * rate

    await state.update_data(quantity=qty, total_price=total)

    preview = (
        f"📦 <b>Order Preview</b>\n\n"
        f"🔸 <b>Service:</b> {service['name']}\n"
        f"🔗 <b>Link:</b> {data['link']}\n"
        f"🔢 <b>Quantity:</b> {qty}\n"
        f"💰 <b>Total Price:</b> ₹{total:.2f}\n\n"
        f"Do you want to confirm this order?"
    )

    await state.set_state(OrderStates.confirm_order)
    await message.answer(preview, reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Confirm Order")], [KeyboardButton(text="❌ Cancel")]],
        resize_keyboard=True
    ))


# === Cancel
@router.message(F.text == "❌ Cancel")
async def cancel_order(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Order cancelled.", reply_markup=ReplyKeyboardRemove())


# === Confirm
@router.message(F.text == "✅ Confirm Order")
async def confirm_order(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id

    # ✅ Calculate total price
    price_per_1000 = float(data['service']['rate'])  # convert string to floa
    quantity = int(data['quantity'])                # also ensure quantity is int
    total_price = (price_per_1000 / 1000) * quantity


    # ✅ Update FSM state and database
    await state.update_data(total_price=total_price)
    cur.execute("UPDATE complaint_tokens SET total_price = ? WHERE token = ?", (total_price, data['token']))
    conn.commit()

    # ✅ Notify user
    await bot.send_message(
        user_id,
        "✅ Your order has been placed successfully!\n"
        "⏳ Please wait while admin reviews it.\n"
        "You’ll be notified once approved or denied."
    )

    # ✅ Prepare admin message
    order_msg = (
        f"📥 <b>New Temp Order (Token)</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"🪙 Token: <code>{data['token']}</code>\n"
        f"🔸 Service: {data['service']['name']}\n"
        f"🔗 Link: {data['link']}\n"
        f"🔢 Qty: {quantity}\n"
        f"💰 Price: ₹{total_price:.2f}\n\n"
        f"📣 Please confirm this order in panel."
    )

    

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Create Approve / Deny buttons
    buttons = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{user_id}:{data['token']}"),
        InlineKeyboardButton(text="❌ Deny", callback_data=f"deny:{user_id}:{data['token']}")
    ]
])
    await bot.send_message(GROUP_ID, order_msg, reply_markup=buttons)
    

from aiogram.types import CallbackQuery
import aiohttp

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


# === Approve Order Callback ===
@router.callback_query(F.data.startswith("approve:"))
async def approve_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⚠️ You're not authorized to do this.", show_alert=True)
state = FSMContext(bot=bot, storage=dp.storage, chat_id=callback.message.chat.id, user_id=user_id)
data = await state.get_data()

    # Extract user_id and token from callback_data
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.message.edit_text("❌ Invalid callback data format.")

    user_id = int(parts[1])
    token = parts[2]

    # Fetch token details safely
    cur.execute("""
        SELECT amount, total_price 
        FROM complaint_tokens 
        WHERE token = ? AND status = 'pending'
    """, (token,))
    row = cur.fetchone()

    if not row:
        return await callback.message.edit_text("❌ No pending token found for this user/token.")

    amount, total_price = row

    # Error handling if total_price is missing
    if total_price is None:
        return await callback.message.edit_text("❌ Cannot approve: total price not found.")

    # Balance deduction
    new_balance = amount - total_price
    if new_balance < 0:
        return await callback.message.edit_text("⚠️ Insufficient balance for this order.")

    # Update DB: mark token approved, update balance
    cur.execute("""
        UPDATE complaint_tokens 
        SET amount = ?, status = 'approved' 
        WHERE token = ?
    """, (new_balance, token))
    conn.commit()

    # Notify user
    await bot.send_message(
        user_id,
        f"✅ Your temp order has been approved by the admin.\n"
        f"💸 ₹{total_price:.2f} has been deducted from your wallet."
    )

    # Update admin message
    await callback.message.edit_text("✅ Order approved successfully.")




    # Deduct balance
    cur.execute("UPDATE complaint_tokens SET amount = ? WHERE token = ?", (new_balance, token))
    conn.commit()

    # Send order to API
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "key": API_KEY,
                "action": "add",
                "service": data['service']['id'],
                "link": data['link'],
                "quantity": data['quantity']
            }
            async with session.post(API_URL, data=payload) as resp:
                api_result = await resp.json()
    except Exception as e:
        return await callback.message.edit_text(f"❌ Failed to send order to API:\n<code>{e}</code>", parse_mode="HTML")

    # Notify user
    await bot.send_message(
        user_id,
        f"✅ Your temp order has been approved by the admin.\n"
        f"💸 ₹{total_price:.2f} has been deducted from your wallet.\n"
        f"📦 Order ID: {api_result.get('order', 'N/A')}"
    )

    # Save to temp_orders table
    cur.execute("""
        INSERT INTO temp_orders (token, user_id, service_name, link, quantity, price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        token, user_id, data['service']['name'],
        data['link'], data['quantity'], total_price
    ))
    conn.commit()

    # Edit admin message
    await callback.message.edit_text(f"✅ Approved by admin\n\n" + callback.message.text, parse_mode="HTML")


# === Deny Order Callback ===
@router.callback_query(F.data.startswith("deny:"))
async def deny_order(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⚠️ You're not authorized to do this.", show_alert=True)

    await bot.send_message(user_id, "❌ Your order was denied by the admin.")
    await callback.message.edit_text("❌ Denied by admin\n\n" + callback.message.text, parse_mode="HTML")
    await callback.answer("❌ Order denied.")


    

    # Save to DB
    cur.execute("""
        INSERT INTO temp_orders (token, user_id, service_name, link, quantity, price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        data['token'], data['user_id'], data['service']['name'],
        data['link'], data['quantity'], data['total_price']
    ))
    conn.commit()

    await message.answer("✅ Order sent to admin for approval.\n⏳ Please wait...", reply_markup=ReplyKeyboardRemove())
    await state.clear()


# === Debug API Command
@router.message(Command("debug_api"))
async def debug_api(message: Message):
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, data={"key": API_KEY, "action": "services"}) as resp:
            raw = await resp.text()
            await message.answer(f"<b>🔍 API Raw Response:</b>\n<code>{raw[:4000]}</code>", parse_mode="HTML")


# === MAIN
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
