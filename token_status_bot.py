# token_status_bot.py

import logging
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart
from dotenv import load_dotenv
import os
import random
import string

# Load env
load_dotenv()

BOT_TOKEN = "5925186202:AAH64rf6SQqYSFw3pC-DrfEs0eOg-QLrU1I"
GROUP_ID = int(os.getenv("GROUP_ID"))
API_KEY = os.getenv("SMM_API_KEY")
API_URL = os.getenv("SMM_API_URL")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# FSM
class OrderStates(StatesGroup):
    browsing_services = State()
    entering_link = State()
    entering_quantity = State()
    confirm_order = State()


# Start command
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    token = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    amount = random.randint(30, 100)  # Simulate wallet amount
    txn_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

    await state.set_data({
        "token": token,
        "amount": amount,
        "txn_id": txn_id,
        "user_id": message.from_user.id
    })

    await message.answer(
        f"✅ Token verified!\n\n"
        f"💼 Temporary Wallet: ₹{amount}\n"
        f"🧾 TXN ID: <code>{txn_id}</code>\n\n"
        "Choose an option below:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💼 My Wallet", callback_data="wallet")],
                [InlineKeyboardButton(text="🛒 New Order", callback_data="new_order")]
            ]
        )
    )

# Wallet
@dp.callback_query(F.data == "wallet")
async def wallet_info(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    await call.message.answer(f"💼 Your temporary wallet balance is ₹{amount}")

# New Order
@dp.callback_query(F.data == "new_order")
async def start_order(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.browsing_services)
    await show_services(call.message, state, page=1)

# Show services
async def show_services(message: types.Message, state: FSMContext, page: int):
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, data={"key": API_KEY, "action": "services"}) as resp:
            services = await resp.json()

    per_page = 8
    total = len(services)
    start = (page - 1) * per_page
    end = start + per_page
    current_services = services[start:end]

    kb = InlineKeyboardBuilder()
    for svc in current_services:
        profit_rate = round(float(svc['rate']) * 1.10, 2)
        kb.button(
            text=f"{svc['name']} | ₹{profit_rate}/1k",
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
    await message.answer("🏪 Choose a service:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("page_"))
async def paginate_services(call: types.CallbackQuery, state: FSMContext):
    page = int(call.data.split("_")[1])
    await show_services(call.message, state, page)

@dp.callback_query(F.data.startswith("svc_"))
async def service_selected(call: types.CallbackQuery, state: FSMContext):
    service_id = int(call.data.split("_")[1])
    data = await state.get_data()
    all_services = data.get("all_services")
    service = next((s for s in all_services if s['service'] == service_id), None)
    if not service:
        return await call.message.answer("Service not found.")

    profit_rate = round(float(service['rate']) * 1.10, 2)
    await state.update_data(service=service)
    await state.set_state(OrderStates.entering_link)

    desc = (
        f"🛎 <b>{service['name']}</b>\n"
        f"💸 Price per 1k: ₹{profit_rate}\n"
        f"🔢 Min: {service['min']} | Max: {service['max']}\n"
        f"🚀 Speed: {service.get('speed', 'N/A')}\n"
        f"ℹ️ Description: {service.get('desc', 'No description available')}\n\n"
        "Please send the link to proceed."
    )
    await call.message.answer(desc)

@dp.message(OrderStates.entering_link)
async def handle_link(message: types.Message, state: FSMContext):
    await state.update_data(link=message.text.strip())
    await state.set_state(OrderStates.entering_quantity)
    await message.answer("📦 Enter the quantity:")

@dp.message(OrderStates.entering_quantity)
async def handle_quantity(message: types.Message, state: FSMContext):
    qty = int(message.text.strip())
    data = await state.get_data()
    service = data['service']
    rate = round(float(service['rate']) * 1.10, 2)
    total_price = (qty / 1000) * rate
    await state.update_data(quantity=qty, total_price=total_price)

    desc = (
        f"🧾 <b>Order Preview:</b>\n\n"
        f"📦 Service: {service['name']}\n"
        f"🔗 Link: {data['link']}\n"
        f"🔢 Quantity: {qty}\n"
        f"💰 Price: ₹{total_price:.2f}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order")]
    ])
    await state.set_state(OrderStates.confirm_order)
    await message.answer(desc, reply_markup=kb)

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Order cancelled.")

@dp.callback_query(F.data == "confirm_order")
async def confirm_order(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']
    token = data['token']
    link = data['link']
    qty = data['quantity']
    service = data['service']
    total_price = data['total_price']

    msg = (
        f"🆕 <b>New Temp Order (Token)</b>\n\n"
        f"🧑 User ID: <code>{user_id}</code>\n"
        f"🔑 Token: <code>{token}</code>\n"
        f"📦 Service: {service['name']}\n"
        f"🔗 Link: {link}\n"
        f"🔢 Qty: {qty}\n"
        f"💰 Price: ₹{total_price:.2f}\n\n"
        f"Please confirm or reject this order."
    )

    await bot.send_message(GROUP_ID, msg)
    await call.message.answer("✅ Order sent to admin for approval.\n⏳ Waiting for confirmation...")
    await state.clear()

# Run
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
