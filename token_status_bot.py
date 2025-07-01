import asyncio
import aiohttp
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = "5925186202:AAH64rf6SQqYSFw3pC-DrfEs0eOg-QLrU1I"
API_KEY = os.getenv("SMM_API_KEY")
API_URL = os.getenv("SMM_API_URL")
GROUP_ID = int(os.getenv("SUPPORT_GROUP_ID"))

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

class UserStates(StatesGroup):
    entering_token = State()
    browsing_services = State()
    entering_link = State()
    entering_quantity = State()
    confirm_order = State()

# === Start Command ===
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await message.answer("👋 Welcome! Please enter your token to continue.")
    await state.set_state(UserStates.entering_token)

# === Handle Token ===
@dp.message(UserStates.entering_token)
async def handle_token(message: Message, state: FSMContext):
    token = message.text.strip()
    await state.update_data(token=token, user_id=message.from_user.id)
    await message.answer(
    f"✅ Token verified!\n\n"
    f"💼 Temporary Wallet: ₹{amount}\n"
    f"🧾 TXN ID: <code>{txn_id}</code>\n\n"
    "Choose an option:",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 My Wallet", callback_data="wallet")],
        [InlineKeyboardButton(text="🛒 New Order", callback_data="new_order")]
    ])
)

@dp.callback_query(F.data == "wallet")
async def wallet_info(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await call.message.answer(f"💼 Your wallet is active for Token: <code>{data['token']}</code>")

# === Show Services with Pagination ===
@dp.callback_query(F.data == "new_order")
async def start_order(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.browsing_services)
    await show_services(call.message, state, page=1)

async def show_services(message: Message, state: FSMContext, page: int):
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, data={"key": API_KEY, "action": "services"}) as resp:
            services = await resp.json()

    per_page = 5
    total = len(services)
    start = (page - 1) * per_page
    end = start + per_page
    current_services = services[start:end]

    data = await state.get_data()
    await state.update_data(all_services=services, current_page=page)

    for svc in current_services:
        rate = round(float(svc['rate']) * 1.10, 2)
        text = (
            f"🔹 <b>{svc['name']}</b>\n"
            f"💰 Price: ₹{rate}/1k\n"
            f"📦 Min: {svc['min']} | Max: {svc['max']}\n"
            f"📄 Type: {svc.get('type', 'N/A')}\n"
            f"⚡ Speed: {svc.get('speed', 'N/A')}"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Select", callback_data=f"svc_{svc['service']}")]
        ])
        await message.answer(text, reply_markup=markup)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"page_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"page_{page+1}"))

    if nav:
        await message.answer("📜 Navigate:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[nav]))

@dp.callback_query(F.data.startswith("page_"))
async def paginate_services(call: CallbackQuery, state: FSMContext):
    page = int(call.data.split("_")[1])
    await show_services(call.message, state, page)

@dp.callback_query(F.data.startswith("svc_"))
async def service_selected(call: CallbackQuery, state: FSMContext):
    service_id = int(call.data.split("_")[1])
    data = await state.get_data()
    all_services = data.get("all_services")
    service = next((s for s in all_services if s['service'] == service_id), None)
    if not service:
        return await call.message.answer("❌ Service not found.")

    await state.update_data(service=service)
    await state.set_state(UserStates.entering_link)
    await call.message.answer(f"🔗 Enter the link for <b>{service['name']}</b>:")

@dp.message(UserStates.entering_link)
async def handle_link(message: Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    await state.set_state(UserStates.entering_quantity)
    await message.answer("📦 Enter the quantity:")

@dp.message(UserStates.entering_quantity)
async def handle_quantity(message: Message, state: FSMContext):
    qty = int(message.text.strip())
    data = await state.get_data()
    service = data['service']
    price = (qty / 1000) * float(service['rate']) * 1.10

    await state.update_data(quantity=qty, total_price=price)

    desc = (
        f"🧾 <b>Order Summary</b>\n\n"
        f"🔹 Service: {service['name']}\n"
        f"🔗 Link: {data['link']}\n"
        f"📦 Quantity: {qty}\n"
        f"💰 Total: ₹{price:.2f}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order")]
    ])
    await state.set_state(UserStates.confirm_order)
    await message.answer(desc, reply_markup=kb)

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Order cancelled.")

@dp.callback_query(F.data == "confirm_order")
async def confirm_order(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    msg = (
        f"📥 <b>New Temp Order</b>\n\n"
        f"👤 User ID: <code>{data['user_id']}</code>\n"
        f"🔗 Token: <code>{data['token']}</code>\n"
        f"🔹 Service: {data['service']['name']}\n"
        f"🔗 Link: {data['link']}\n"
        f"📦 Quantity: {data['quantity']}\n"
        f"💰 Price: ₹{data['total_price']:.2f}"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data="admin_approve"),
            InlineKeyboardButton(text="❌ Deny", callback_data="admin_deny")
        ]
    ])
    await bot.send_message(GROUP_ID, msg, reply_markup=markup)
    await call.message.answer("✅ Order sent to admin for review.")
    await state.clear()

# === Admin Handling Logic (Optional) ===
@dp.callback_query(F.data.in_(["admin_approve", "admin_deny"]))
async def admin_action(call: CallbackQuery):
    action = "approved" if call.data == "admin_approve" else "denied"
    await call.message.edit_text(call.message.text + f"\n\n✅ Order {action} by admin.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
