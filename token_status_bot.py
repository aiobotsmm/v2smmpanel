import asyncio
import secrets
import sqlite3  # or use mysql.connector for MySQL
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import BotCommand
from aiogram.filters import Command
from aiogram import Router
from aiogram.client.bot import DefaultBotProperties

from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = "5925186202:AAH64rf6SQqYSFw3pC-DrfEs0eOg-QLrU1I"
DATABASE = "yourdb.db"  # update this
GROUP_ID = int(os.getenv("GROUP_ID"))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()
router = Router()
dp.include_router(router)

conn = sqlite3.connect(DATABASE)
cur = conn.cursor()


class OrderStates(StatesGroup):
    waiting_token = State()
    browsing_services = State()
    entering_link = State()
    entering_quantity = State()
    confirm_order = State()


@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await state.set_state(OrderStates.waiting_token)
    await message.answer("🔐 Please enter your 8-digit token to verify.")


@router.message(OrderStates.waiting_token)
async def handle_token(message: Message, state: FSMContext):
    token = message.text.strip().upper()

    cur.execute("SELECT user_id, txn_id, amount FROM complaint_tokens WHERE token = ?", (token,))
    result = cur.fetchone()

    if not result:
        return await message.answer("❌ Invalid token. Please check again.")

    user_id, txn_id, amount = result
    await state.update_data(token=token, user_id=user_id, txn_id=txn_id, amount=amount)

    # Show wallet info + reply keyboard
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


@router.message(F.text == "💼 My Wallet")
async def show_wallet(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", "0.00")
    await message.answer(f"💼 Your current wallet balance is ₹{amount}")


# you can now continue the order flow
# handle "🛒 New Order" to fetch services and process


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
