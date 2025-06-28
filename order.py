from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import requests
from config import SMM_API_KEY, SMM_API_URL, GROUP_ID
from db import cur, conn, bot
from aiogram.filters import Command
from keyboards import main_menu

router = Router()
ADMIN_ID=5274097505
# --- Cancel command ---
@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    if await state.get_state() is None:
        return await message.answer("⚠️ Nothing to cancel.")
    await state.clear()
    await message.answer("❌ Operation cancelled.", reply_markup=main_menu(message.from_user.id))

# --- FSM States ---
class PlaceOrder(StatesGroup):
    svc_id = State()
    svc_name = State()
    svc_rate = State()
    svc_link = State()
    svc_qty = State()

# --- Start Order ---
@router.message(F.text == "📦 New Order")
async def start_order(message: Message, state: FSMContext):
    response = requests.post(SMM_API_URL, data={"key": SMM_API_KEY, "action": "services"})
    if response.status_code != 200:
        return await message.answer("⚠️ Failed to fetch services.")

    services = response.json()
    await state.update_data(services=services)
    await show_services_page(message.chat.id, services, 0)

async def show_services_page(chat_id, services, page: int):
    per_page = 8
    start = page * per_page
    end = start + per_page
    buttons = []

    for svc in services[start:end]:
        buttons.append([InlineKeyboardButton(
            text=f"{svc['name']} ₹{svc['rate']}", callback_data=f"svc_{svc['service']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"page_{page-1}"))
    if end < len(services):
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"page_{page+1}"))
    if nav:
        buttons.append(nav)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(chat_id, f"📋 Choose a service (Page {page+1})", reply_markup=keyboard)

@router.callback_query(F.data.startswith("page_"))
async def paginate_services(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    data = await state.get_data()
    services = data.get("services", [])
    await callback.message.delete()
    await show_services_page(callback.message.chat.id, services, page)
    await callback.answer()

@router.callback_query(F.data.startswith("svc_"))
async def service_detail(callback: CallbackQuery, state: FSMContext):
    svc_id = callback.data.split("_")[1]
    data = await state.get_data()
    services = data.get("services", [])

    svc = next((s for s in services if str(s["service"]) == svc_id), None)
    if not svc:
        return await callback.answer("❌ Service not found", show_alert=True)

    rate_with_profit = round(float(svc['rate']) * 1.10, 2)
    await state.update_data(
        svc_id=svc_id,
        svc_name=svc["name"],
        svc_rate=rate_with_profit,
        svc_min=svc.get("min", "?"),
        svc_max=svc.get("max", "?")
    )

    text = (
        f"📌 *{svc['name']}*\n"
        f"{svc.get('description', 'No description available.')}\n"
        f"💰 Rate: ₹{rate_with_profit} per 1k units\n"
        f"🔢 Min: {svc.get('min', '?')} | Max: {svc.get('max', '?')}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Select", callback_data=f"select_{svc_id}")]
        ]
    )
    await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("select_"))
async def ask_link(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🔗 Please send the link/username for this service.\n\n"
        "❗ You can cancel this operation anytime by typing /cancel."
    )
    await state.set_state(PlaceOrder.svc_link)
    await callback.answer()
  
import re
@router.message(PlaceOrder.svc_link)
async def ask_quantity(message: Message, state: FSMContext):
    link = message.text.strip()

    # --- Basic link validation ---
    if not (re.match(r'https?://', link) or link.startswith("@")):
        return await message.answer(
            "❌ Invalid link. Please send a valid URL (http/https) or @username."
        )

    await state.update_data(svc_link=link)
    await message.answer("📦 Enter quantity required:")
    await state.set_state(PlaceOrder.svc_qty)


@router.message(PlaceOrder.svc_qty)
async def confirm_order(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
        if qty <= 0:
            raise ValueError
    except (ValueError, AssertionError):
        return await message.answer("❌ Invalid quantity. Enter a number greater than 0.")

    await state.update_data(svc_qty=qty)
    data = await state.get_data()
    rate = float(data['svc_rate'])
    cost = round(qty * rate / 1000, 2)

    user_balance = cur.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,)).fetchone()
    if not user_balance or user_balance[0] < cost:
        return await message.answer("❌ Insufficient balance.")

    await state.update_data(svc_qty=qty, svc_cost=cost)

    text = (
        f"⚠️ Please confirm your order:\n\n"
        f"📦 *Service:* {data['svc_name']}\n"
        f"🔗 *Link:* {data['svc_link']}\n"
        f"🔢 *Qty:* {qty}\n"
        f"💰 *Cost:* ₹{cost:.2f}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Confirm Order", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_order")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "confirm_order")
async def place_final_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    try:
        response = requests.post(SMM_API_URL, data={
            "key": SMM_API_KEY,
            "action": "add",
            "service": data['svc_id'],
            "link": data['svc_link'],
            "quantity": data['svc_qty']
        })

        resp_json = response.json()
        if 'order' not in resp_json:
            await callback.message.answer(f"❌ Failed: {resp_json.get('error', 'Unknown error')}")
            await state.clear()
            return

        order_id = str(resp_json['order'])
        cost = data['svc_cost']
        qty = data['svc_qty']

        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (cost, user_id))
        cur.execute("""
            INSERT INTO orders(user_id, order_id, service_name, link, quantity, price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, order_id, data['svc_name'], data['svc_link'], qty, cost, 'pending'))
        conn.commit()

        await callback.message.answer(f"✅ Order placed!\n🆔 ID: {order_id}\n💰 Cost: ₹{cost:.2f}")

        user_row = cur.execute("SELECT name FROM users WHERE user_id=?", (user_id,)).fetchone()
        user_name = user_row[0] if user_row else "Unknown"
        notif_msg = (
            f"📥 *New Order*\n"
            f"👤 `{user_id}` ({user_name})\n"
            f"🆔 Order: `{order_id}`\n"
            f"📦 {data['svc_name']}\n"
            f"🔗 {data['svc_link']}\n"
            f"🔢 Qty: {qty}\n"
            f"💰 ₹{cost:.2f}\n"
            f"⏳ Status: pending"
        )
        await bot.send_message(ADMIN_ID, notif_msg, parse_mode="Markdown")
        await bot.send_message(GROUP_ID, notif_msg, parse_mode="Markdown")

    except Exception as e:
        print(f"❌ Order placement error: {e}")
        await callback.message.answer("❌ Failed to place order. Please try again.")

    await state.clear()

@router.callback_query(F.data == "cancel_order")
async def cancel_order_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("❌ Order cancelled.")
    await state.clear()
