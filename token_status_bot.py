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
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from dotenv import load_dotenv

# === Load .env ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")

# === Bot Init ===
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# === DB Init ===
conn = sqlite3.connect("yourdb.db")
cur = conn.cursor()


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
    token = message.text.strip().upper()

    cur.execute("SELECT user_id, txn_id, amount FROM complaint_tokens WHERE token = ?", (token,))
    result = cur.fetchone()

    if not result:
        return await message.answer("❌ Invalid token. Please check again.")

    user_id, txn_id, amount = result
    await state.update_data(token=token, user_id=user_id, txn_id=txn_id, amount=amount)

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

    per_page = 5
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

    # Send to admin
    order_msg = (
        f"📥 <b>New Temp Order (Token)</b>\n\n"
        f"👤 User ID: <code>{data['user_id']}</code>\n"
        f"🪙 Token: <code>{data['token']}</code>\n"
        f"🔸 Service: {data['service']['name']}\n"
        f"🔗 Link: {data['link']}\n"
        f"🔢 Qty: {data['quantity']}\n"
        f"💰 Price: ₹{data['total_price']:.2f}\n\n"
        f"📣 Please confirm this order in panel."
    )

    await bot.send_message(GROUP_ID, order_msg)

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
