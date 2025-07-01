import os
import sqlite3
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp

# === Load ENV ===
load_dotenv()
BOT_TOKEN = "5925186202:AAH64rf6SQqYSFw3pC-DrfEs0eOg-QLrU1I"
API_KEY = os.getenv("SMM_API_KEY")
API_URL = os.getenv("SMM_API_URL")
GROUP_ID = -1002897201960  # Hardcoded group
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cur = conn.cursor()

# === States ===
class OrderStates(StatesGroup):
    awaiting_token = State()
    browsing_services = State()
    entering_link = State()
    entering_quantity = State()
    confirm_order = State()

# === Start ===
@dp.message(F.text == "/start")
async def start_handler(message: types.Message, state: FSMContext):
    await state.set_state(OrderStates.awaiting_token)
    await message.answer(
        "⚠️ <b>Sorry for the delay in payment approval.</b>\n\n"
        "Please enter your <b>complaint token</b> to continue.",
        parse_mode="HTML"
    )

# === Step 1: Enter Token ===
@dp.message(OrderStates.awaiting_token)
async def handle_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    cur.execute("SELECT user_id, amount, txn_id FROM complaint_tokens WHERE token = ?", (token,))
    row = cur.fetchone()
    if not row:
        return await message.answer("\u274c Invalid or expired token. Please try again.")

    user_id, amount, txn_id = row
    await state.update_data(token=token, user_id=user_id, amount=amount, txn_id=txn_id)

    await message.answer(
    f"✅ Temporary Wallet: ₹{amount}\n🧾 TXN ID: <code>{txn_id}</code>\n\n"
    "Choose an option below:",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 My Wallet", callback_data="wallet")],
        [InlineKeyboardButton(text="🛒 New Order", callback_data="new_order")]
    ])
)

# === Wallet Info ===
@dp.callback_query(F.data == "wallet")
async def wallet_info(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    await call.message.edit_text(f"💼 Your temporary wallet balance is ₹{amount}")




# === Start Order Process ===
@dp.callback_query(F.data == "new_order")
async def start_order(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not all(k in data for k in ("user_id", "token", "amount")):
        return await call.message.answer("❌ Missing token session. Please /start again.")

    await state.set_state(OrderStates.browsing_services)
    await show_services(call.message, state, page=1)

# === Show SMM Services with Pagination ===
async def show_services(message: types.Message, state: FSMContext, page: int):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, data={"key": API_KEY, "action": "services"}) as resp:
                services = await resp.json()
    except Exception as e:
        return await message.answer(f"❌ Failed to load services.\n{str(e)}")

    if not services:
        return await message.answer("❌ No services found from API.")

    per_page = 8
    total = len(services)
    start = (page - 1) * per_page
    end = start + per_page
    current_services = services[start:end]

    kb = InlineKeyboardBuilder()
    for svc in current_services:
        kb.button(
            text=f"{svc['name']} - ₹{svc['rate']}/1k",
            callback_data=f"svc_{svc['service']}"
        )

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"page_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"page_{page+1}"))
    if nav:
        kb.row(*nav)

    await state.update_data(all_services=services, current_page=page)
    await message.edit_text("📋 Select a service to order:", reply_markup=kb.as_markup())

# === Pagination for Services ===
@dp.callback_query(F.data.startswith("page_"))
async def paginate_services(call: types.CallbackQuery, state: FSMContext):
    page = int(call.data.split("_")[1])
    await show_services(call.message, state, page)

# === When a Service is Selected ===
@dp.callback_query(F.data.startswith("svc_"))
async def service_selected(call: types.CallbackQuery, state: FSMContext):
    service_id = int(call.data.split("_")[1])
    data = await state.get_data()
    all_services = data.get("all_services", [])

    service = next((s for s in all_services if int(s['service']) == service_id), None)
    if not service:
        return await call.message.answer("❌ Service not found.")

    await state.update_data(service=service)
    await state.set_state(OrderStates.entering_link)
    await call.message.answer(f"🔗 Please enter the link for <b>{service['name']}</b>")

# === User Enters Link ===
@dp.message(OrderStates.entering_link)
async def handle_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    await state.set_state(OrderStates.entering_quantity)
    await message.answer("🔢 Enter the quantity:")

# === User Enters Quantity ===
@dp.message(OrderStates.entering_quantity)
async def handle_quantity(message: types.Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
    except ValueError:
        return await message.answer("❌ Invalid quantity. Please enter a number.")

    data = await state.get_data()
    service = data['service']
    total_price = (qty / 1000) * float(service['rate'])
    await state.update_data(quantity=qty, total_price=total_price)

    desc = (
        f"🧾 <b>Order Preview:</b>\n"
        f"🛎️ Service: <b>{service['name']}</b>\n"
        f"🔗 Link: <code>{data['link']}</code>\n"
        f"🔢 Quantity: {qty}\n"
        f"💰 Total Price: ₹{total_price:.2f}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm Order", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Cancel Order", callback_data="cancel_order")]
    ])

    await state.set_state(OrderStates.confirm_order)
    await message.answer(desc, reply_markup=kb)

# === Cancel Order ===
@dp.callback_query(F.data == "cancel_order")
async def cancel_order(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Your order has been cancelled.")

# === Confirm Order and Notify Admin ===
@dp.callback_query(F.data == "confirm_order")
async def confirm_order(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.from_user.id
    token = data.get("token", "unknown")
    service = data["service"]
    link = data["link"]
    qty = data["quantity"]
    total_price = data["total_price"]

    order_text = (
        f"📥 <b>New Token Order</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"🔑 Token: <code>{token}</code>\n"
        f"🛎️ Service: {service['name']}\n"
        f"🔗 Link: {link}\n"
        f"🔢 Quantity: {qty}\n"
        f"💰 Price: ₹{total_price:.2f}\n\n"
        "✅ Please approve or reject this order."
    )

    await bot.send_message(GROUP_ID, order_text)
    await call.message.edit_text("✅ Order sent to admin.\n⏳ Waiting for confirmation...")
    await state.clear()



# === Run Bot ===
import asyncio

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

