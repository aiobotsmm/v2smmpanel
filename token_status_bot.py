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
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from db import cur, conn

# === Load .env ===
load_dotenv()
BOT_TOKEN = "5925186202:AAH64rf6SQqYSFw3pC-DrfEs0eOg-QLrU1I"
GROUP_ID = int(os.getenv("GROUP_ID"))
API_URL = os.getenv("SMM_API_URL")
API_KEY = os.getenv("SMM_API_KEY")
ADMIN_ID = 5274097505


# === Bot Init ===
from aiogram.client.default import DefaultBotProperties

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
router = Router()
dp.include_router(router)

# === FSM States ===
class OrderStates(StatesGroup):
    waiting_token = State()
    browsing_services = State()
    entering_link = State()
    entering_quantity = State()
    confirm_order = State()


# === /start Command ===
@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(OrderStates.waiting_token)
    await message.answer("🔐 Please enter your 8-digit token to verify.")


# === Token Verification ===
@router.message(OrderStates.waiting_token)
async def handle_token(message: Message, state: FSMContext):
    token = message.text.strip()
    cur.execute("SELECT user_id, txn_id, amount FROM complaint_tokens WHERE token = ?", (token,))
    row = cur.fetchone()

    if not row:
        return await message.answer("❌ Invalid or expired token. Please try again.")

    user_id, txn_id, amount = row

    # Save token info in FSM
    await state.update_data(
        token=token,
        user_id=user_id,
        txn_id=txn_id,
        amount=amount
    )

    # Show wallet info
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
        f"👤 User ID: <code>{user_id}</code>\n"
        f"💼 Wallet Balance: ₹{amount}\n"
        f"🧾 TXN ID: <code>{txn_id}</code>\n\n"
        f"Please choose an option below:",
        reply_markup=keyboard
    )

# === Wallet Check ===
@router.message(F.text == "💼 My Wallet")
async def show_wallet(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")

    if amount is None:
        return await message.answer("⚠️ Wallet info not available. Please verify your token first using /start.")

    await message.answer(f"💼 Your current wallet balance is ₹{float(amount):.2f}")


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
    await message.answer(
        text + "\nTap a service to view more ↓",
        reply_markup=ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)
    )


# === Pagination Navigation ===
@router.message(F.text.startswith("⬅️") | F.text.startswith("➡️"))
async def handle_pagination(message: Message, state: FSMContext):
    try:
        page = int(message.text.split("Page")[1].strip())
        await show_services(message, state, page)
    except Exception:
        await message.answer("❌ Invalid page navigation.")


# === Show Single Service ===
@router.message(OrderStates.browsing_services)
async def service_detail(message: Message, state: FSMContext):
    data = await state.get_data()
    all_services = data.get("all_services", [])
    svc_name = message.text.strip()

    matched = next((s for s in all_services if s["name"].lower() == svc_name.lower()), None)
    if not matched:
        return await message.answer("❌ Service not found. Please try again.")

    rate = round(float(matched['rate']) * 1.1, 2)
    desc = (
        f"📝 <b>Service Details:</b>\n\n"
        f"🔸 <b>Name:</b> {matched['name']}\n"
        f"💰 <b>Price:</b> ₹{rate}/1k\n"
        f"📉 <b>Min:</b> {matched.get('min')}, 📈 <b>Max:</b> {matched.get('max')}\n"
        f"⚡ <b>Speed:</b> {matched.get('speed') or 'N/A'}\n"
        f"ℹ️ <b>Desc:</b> {matched.get('desc') or 'No description'}\n\n"
        f"👉 Press '✅ Continue' to enter link."
    )

    await state.update_data(service=matched)
    await state.set_state(OrderStates.entering_link)

    await message.answer(desc, reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Continue")],
            [KeyboardButton(text="⬅️ Back to Services")]
        ],
        resize_keyboard=True
    ))

# === Ask for Link
@router.message(OrderStates.entering_link, F.text == "✅ Continue")
async def ask_link(message: Message, state: FSMContext):
    await message.answer("🔗 Please enter the link for this order:", reply_markup=ReplyKeyboardRemove())


# === Receive Link
# === Receive Link (accepts @username or valid URL)
@router.message(OrderStates.entering_link)
async def receive_link(message: Message, state: FSMContext):
    link = message.text.strip()

    # ✅ Accept @username or valid URL
    if not (link.startswith("@") or link.startswith("http://") or link.startswith("https://")):
        return await message.answer("❌ Please enter a valid link or username (starting with @).")

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
    service = data.get("service")
    if not service:
        return await message.answer("❌ Something went wrong. Please start again.")

    rate = round(float(service["rate"]) * 1.1, 2)
    total = round((qty / 1000) * rate, 2)

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
        keyboard=[
            [KeyboardButton(text="✅ Confirm Order")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True
    ))


# === Cancel
@router.message(F.text == "❌ Cancel")
async def cancel_order(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Order cancelled.", reply_markup=ReplyKeyboardRemove())


# === Confirm Order ===
@router.message(F.text == "✅ Confirm Order")
async def confirm_order(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id

    token = data.get("token")
    service = data.get("service")
    quantity = data.get("quantity")
    link = data.get("link")

    if not all([token, service, quantity, link]):
        return await message.answer("❌ Missing order details. Please try again.")

    try:
        price_per_1000 = float(service["rate"])
        quantity = int(quantity)
        total_price = round((price_per_1000 / 1000) * quantity, 2)
    except Exception as e:
        return await message.answer(f"❌ Failed to calculate price.\n{e}")

    # Save price
    await state.update_data(total_price=total_price)
    cur.execute("UPDATE complaint_tokens SET total_price = ? WHERE token = ?", (total_price, token))
    conn.commit()

    await bot.send_message(
        user_id,
        "✅ Your order has been placed successfully!\n⏳ Please wait while admin reviews it."
    )

    # Send admin alert
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"approve:{user_id}:{token}"),
            InlineKeyboardButton(text="❌ Deny", callback_data=f"deny:{user_id}:{token}")
        ]
    ])

    await bot.send_message(GROUP_ID, (
        f"📥 <b>New Temp Order</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"🪙 Token: <code>{token}</code>\n"
        f"🔸 Service: {service['name']}\n"
        f"🔗 Link: {link}\n"
        f"🔢 Qty: {quantity}\n"
        f"💰 Total: ₹{total_price:.2f}"
    ), reply_markup=buttons)

@router.callback_query(F.data.startswith("approve:"))
async def approve_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⚠️ You're not authorized to do this.", show_alert=True)

    _, user_id_str, token = callback.data.split(":")
    user_id = int(user_id_str)

    # Access FSM storage
    key = StorageKey(bot_id=callback.bot.id, chat_id=user_id, user_id=user_id)
    state = FSMContext(storage=dp.storage, key=key)
    data = await state.get_data()

    # Validate required data
    required_fields = ["token", "service", "link", "quantity", "total_price"]
    if not all(field in data for field in required_fields):
        return await callback.message.answer("❌ Missing order data in user session.")

    # Double-check token in DB
    cur.execute("SELECT amount, total_price FROM complaint_tokens WHERE token = ?", (token,))
    row = cur.fetchone()
    if not row:
        return await callback.message.answer("❌ No pending token found in DB.")

    amount, total_price = row
    if total_price is None:
        return await callback.message.answer("❌ Cannot approve: total price not found.")

    if amount < total_price:
        return await callback.message.answer("⚠️ Insufficient balance for approval.")

    new_balance = amount - total_price

    # === 1. Update DB: mark approved and deduct balance
    cur.execute("UPDATE complaint_tokens SET amount = ?, status = 'approved' WHERE token = ?", (new_balance, token))
    conn.commit()


    # === 2. Send to SMM API
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "key": API_KEY,
                "action": "add",
                "service": data['service'].get('id') or data['service'].get('service'),
                "link": data['link'],
                "quantity": data['quantity']
            }
            async with session.post(API_URL, data=payload) as resp:
                api_result = await resp.json()

        if "error" in api_result:
            return await callback.message.edit_text(f"❌ API Error: <code>{api_result['error']}</code>", parse_mode="HTML")

        order_id = api_result.get("order", "N/A")

    except Exception as e:
        return await callback.message.edit_text(f"❌ Failed to send order to API:\n<code>{e}</code>", parse_mode="HTML")

    # === 3. Notify user
    await bot.send_message(
        user_id,
        f"✅ Your order has been approved by the admin.\n"
        f"💸 ₹{total_price:.2f} has been deducted from your wallet.\n"
        f"📦 API Order ID: <code>{order_id}</code>"
    )

    # === 4. Save to temp_orders table
    cur.execute("""
        INSERT INTO temp_orders (token, user_id, service_name, link, quantity, price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        token, user_id, data['service']['name'], data['link'],
        data['quantity'], total_price
    ))
    conn.commit()

    # === 5. Update admin message
    await callback.message.edit_text(
        f"✅ Approved by admin\n\n{callback.message.text}",
        parse_mode="HTML"
    )
@router.callback_query(F.data.startswith("deny:"))
async def deny_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⚠️ You're not authorized to do this.", show_alert=True)

    # Extract user ID and token from callback
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("❌ Invalid deny data format.")

    user_id = int(parts[1])
    token = parts[2]

    # Get user FSM data
    key = StorageKey(bot_id=callback.bot.id, chat_id=user_id, user_id=user_id)
    state = FSMContext(storage=dp.storage, key=key)
    data = await state.get_data()

    required = ['token', 'user_id', 'service', 'link', 'quantity', 'total_price']
    if not all(k in data for k in required):
        return await callback.message.answer("❌ Missing user order data.")

    # Notify user
    await bot.send_message(user_id, "❌ Your order was denied by the admin.")

    # Save denial to temp_orders
    cur.execute("""
        INSERT INTO temp_orders (token, user_id, service_name, link, quantity, price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        data['token'], data['user_id'], data['service']['name'],
        data['link'], data['quantity'], data['total_price']
    ))
    conn.commit()

    # Edit admin message
    await callback.message.edit_text("❌ Denied by admin\n\n" + callback.message.text, parse_mode="HTML")

    await callback.answer("❌ Order denied.")

# === Debug API Command ===
@router.message(Command("debug_api"))
async def debug_api(message: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, data={"key": API_KEY, "action": "services"}) as resp:
                raw = await resp.text()
                if resp.status != 200:
                    return await message.answer(f"❌ API Error {resp.status}:\n<code>{raw[:4000]}</code>", parse_mode="HTML")

                await message.answer(f"<b>🔍 API Raw Response:</b>\n<code>{raw[:4000]}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Error contacting API:\n<code>{e}</code>", parse_mode="HTML")

#----------------user orders -----------------#
@router.message(Command("userorders"))
async def check_token_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⚠️ You're not authorized to use this command.")

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            return await message.answer("❌ Usage: /userorders <token>")

        token = parts[1]

        cur.execute("SELECT user_id, amount, total_price FROM complaint_tokens WHERE token = ?", (token,))
        row = cur.fetchone()

        if not row:
            return await message.answer("❌ No data found for this token.")

        user_id, amount, total = row
        remaining = round(amount - (total or 0), 2)

        cur.execute("SELECT COUNT(*) FROM temp_orders WHERE token = ?", (token,))
        order_count = cur.fetchone()[0]

        msg = (
            f"📊 <b>Token Order Summary</b>\n\n"
            f"🪙 Token: <code>{token}</code>\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"💸 Used: ₹{total or 0:.2f}\n"
            f"💼 Remaining: ₹{remaining:.2f}\n"
            f"📦 Orders Placed: {order_count}"
        )
        await message.answer(msg)

    except Exception as e:
        await message.answer(f"⚠️ Error: {e}")

#-----------------expiry token------------------#
@router.message(Command("expiretoken"))
async def expire_token_cmd(message: Message):
    args = message.text.split()
    if len(args) != 2:
        return await message.answer("❌ Usage: /expiretoken <token_id>")

    token = args[1].strip()

    cur.execute("SELECT user_id, status FROM complaint_tokens WHERE token = ?", (token,))
    row = cur.fetchone()

    if not row:
        return await message.answer("❌ No token found with this token ID.")

    user_id, status = row

    if status == "expired":
        return await message.answer("⚠️ This token is already expired.")
    
    # Optional: Warn for approved tokens but still allow expiration
    if status == "approved":
        await message.answer("⚠️ This token was already approved. Proceeding to mark as expired...")

    # Expire it
    cur.execute("UPDATE complaint_tokens SET status = 'expired' WHERE token = ?", (token,))
    conn.commit()

    await bot.send_message(
        user_id,
        "🕓 Your token has been marked as expired by the admin.\n✅ Your complaint is considered resolved. You may now generate a new one if needed."
    )
    await message.answer(f"✅ Token <code>{token}</code> is now expired and user has been notified.")

except Exception as e:
        await message.answer(f"❌ Error: {e}")

# === MAIN ENTRY ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

