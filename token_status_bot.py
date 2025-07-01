import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from dotenv import load_dotenv
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command
import os
import random

# === Load .env
load_dotenv()

# === Constants from .env
BOT_TOKEN = "5925186202:AAH64rf6SQqYSFw3pC-DrfEs0eOg-QLrU1I"
API_KEY = os.getenv("SMM_API_KEY")
API_URL = os.getenv("SMM_API_URL")
GROUP_ID = int(os.getenv("GROUP_ID"))

# === Init
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# === FSM States
class OrderStates(StatesGroup):
    waiting_token = State()
    main_menu = State()
    browsing_services = State()
    confirming_service = State()
    entering_link = State()
    entering_quantity = State()
    confirm_order = State()

# === TEMP DB
USER_DB = {}  # {user_id: {'token': xxx, 'amount': xxx, 'txn_id': xxx}}

# === /start
@router.message(Command("start"))
async def handle_token(message: Message, state: FSMContext):
    await message.answer("🔑 Please enter your token to proceed:")
    await state.set_state(OrderStates.awaiting_token)

@router.message(OrderStates.waiting_token)
async def verify_token(message: Message, state: FSMContext):
    token = message.text.strip()

    # ✅ 1. Fetch wallet data from your DB/API using the token
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://yourdomain/api/token_verify", data={"token": token}) as resp:
                data = await resp.json()
    except Exception:
        return await message.answer("❌ Failed to fetch data. Please try again later.")

    # ✅ 2. Check if token is valid and extract amount/txn_id
    if not data.get("status") == "success":
        return await message.answer("❌ Invalid token!")

    amount = data.get("amount")
    txn_id = data.get("txn_id")

    if not amount or not txn_id:
        return await message.answer("⚠️ Could not fetch wallet info.")

    # ✅ 3. Save in memory
    user_id = message.from_user.id
    USER_DB[user_id] = {
        "token": token,
        "amount": amount,
        "txn_id": txn_id,
    }

    await state.clear()
    await message.answer(
        f"✅ Token verified!\n\n"
        f"💼 Temporary Wallet: ₹{amount}\n"
        f"🧾 TXN ID: <code>{txn_id}</code>\n\n"
        "Choose an option:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🧾 My Wallet")], [KeyboardButton(text="🆕 New Order")]],
            resize_keyboard=True
        )
    )


# === My Wallet
@router.message(F.text == "👜 My Wallet")
async def wallet(message: Message):
    user_data = USER_DB.get(message.from_user.id)
    if not user_data:
        return await message.answer("❌ Token not found. Please use /start again.")

    await message.answer(f"💰 Your Wallet Balance: ₹{user_data['amount']}")

# === New Order Menu
@router.message(F.text == "🆕 New Order")
async def start_order(message: Message, state: FSMContext):
    await state.set_state(OrderStates.browsing_services)
    await show_services(message, state, page=1)

# === Show Services with Pagination (Vertical List)
async def show_services(message: Message, state: FSMContext, page: int):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(API_URL, data={"key": API_KEY, "action": "services"}) as resp:
                services = await resp.json()
        except Exception:
            return await message.answer("⚠️ Failed to fetch services. Please try again later.")

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
        rate = round(float(svc['rate']) * 1.1, 2)  # add 10%
        text += f"🔹 {svc['name']} - ₹{rate}/1k\n"
        btns.append([KeyboardButton(text=f"{svc['name']}")])

    # Pagination
    if page > 1:
        btns.append([KeyboardButton(text=f"⬅️ Prev Page {page-1}")])
    if end < total:
        btns.append([KeyboardButton(text=f"➡️ Next Page {page+1}")])

    await state.update_data(all_services=services, current_page=page)
    markup = ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)
    await message.answer(text + "\nTap a service to view more ↓", reply_markup=markup)

# === Pagination handler
@router.message(F.text.startswith("⬅️") | F.text.startswith("➡️"))
async def handle_pagination(message: Message, state: FSMContext):
    parts = message.text.split("Page")
    if len(parts) == 2:
        page = int(parts[1].strip())
        await show_services(message, state, page=page)

# === Handle service selection → show full description
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

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Continue")], [KeyboardButton(text="⬅️ Back to Services")]],
        resize_keyboard=True
    )

    await state.update_data(service=matched)
    await state.set_state(OrderStates.entering_link)
    await message.answer(desc, reply_markup=kb)

# === Back to Services
@router.message(F.text == "⬅️ Back to Services")
async def go_back_to_services(message: Message, state: FSMContext):
    data = await state.get_data()
    page = data.get("current_page", 1)
    await show_services(message, state, page)

# === Enter link
@router.message(OrderStates.entering_link, F.text == "✅ Continue")
async def ask_link(message: Message, state: FSMContext):
    await message.answer("🔗 Please enter the link for this order:", reply_markup=ReplyKeyboardRemove())

@router.message(OrderStates.entering_link)
async def receive_link(message: Message, state: FSMContext):
    link = message.text.strip()
    await state.update_data(link=link)
    await state.set_state(OrderStates.entering_quantity)
    await message.answer("🔢 Enter the quantity you want:")

# === Enter quantity
@router.message(OrderStates.entering_quantity)
async def receive_quantity(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Please enter a valid number.")

    data = await state.get_data()
    service = data["service"]
    rate = round(float(service["rate"]) * 1.1, 2)  # 10% profit
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

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Confirm Order")],
            [KeyboardButton(text="❌ Cancel")]
        ],
        resize_keyboard=True
    )

    await state.set_state(OrderStates.confirm_order)
    await message.answer(preview, reply_markup=kb)

# === Cancel order
@router.message(F.text == "❌ Cancel")
async def cancel_order(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Order cancelled.", reply_markup=ReplyKeyboardRemove())

# === Confirm order
@router.message(F.text == "✅ Confirm Order")
async def confirm_order(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    user_data = USER_DB.get(user_id)

    if not user_data:
        return await message.answer("❌ Token expired. Please /start again.")

    order_msg = (
        f"📥 <b>New Temp Order (Token)</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"🪙 Token: <code>{user_data['token']}</code>\n"
        f"🔸 Service: {data['service']['name']}\n"
        f"🔗 Link: {data['link']}\n"
        f"🔢 Qty: {data['quantity']}\n"
        f"💰 Price: ₹{data['total_price']:.2f}\n\n"
        f"📣 Please confirm this order in panel."
    )

    await bot.send_message(GROUP_ID, order_msg)
    await message.answer("✅ Order sent to admin for approval.\n⏳ Please wait...", reply_markup=ReplyKeyboardRemove())
    await state.clear()

# === MAIN
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
