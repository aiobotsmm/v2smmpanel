# main.py

import asyncio
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# Load .env variables
load_dotenv()

# Configs & DB
from config import API_TOKEN
from db import conn, cur, initialize_database

# Routers
from adminbutton import router as admin_button_router
from user_routes import router as user_router
from admin import admin_router
from order import router as order_router
from my_orders import router as my_orders_router
from wallet_balance import router as wallet_router
from auto_order_updater import auto_update_orders
from groupdata import group_router
from admin_contact import contact_router
#from contact import router as con_router
#from admin import router as admin_router
# from cancel import cancel_router  # Optional if you separate cancel handler
#---auto token---#
import secrets
import datetime
from asyncio import sleep
# Group ID where admin notifications go
GROUP_ID = -1002897201960  # Replace with your actual group ID

async def auto_generate_tokens():
    while True:
        # ⏳ Check pending payments older than 60 min
        from datetime import datetime, timedelta, timezone
        sixty_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=1)

        cur.execute("""
            SELECT user_id, txn_id, amount FROM payments
            WHERE status = 'pending' AND created_at <= ?
        """, (sixty_minutes_ago,))
        old_payments = cur.fetchall()

        for user_id, txn_id, amount in old_payments:
            # Check if token already exists
            cur.execute("SELECT 1 FROM complaint_tokens WHERE txn_id = ?", (txn_id,))
            if cur.fetchone():
                continue  # Token already generated

            # 🔐 Generate token
            token = secrets.token_hex(4).upper()

            # Save token
            cur.execute("""
                INSERT INTO complaint_tokens (token, user_id, txn_id, amount)
                VALUES (?, ?, ?, ?)
            """, (token, user_id, txn_id, amount))
            conn.commit()

            # Notify user
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Inline button to open your token support bot
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚀 Use Token in Support Bot", url="https://t.me/smmtokendesk_bot")]
])

# Notify user
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Inline button to open your token support bot
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚀 Use Token in Support Bot", url="https://t.me/smmtokendesk_bot")]
])

# Notify user
try:
    await bot.send_message(
        chat_id=user_id,
        text=(
            "⚠️ <b>Payment Timeout</b>\n\n"
            f"🔐 <b>Token:</b> <code>{token}</code>\n"
            f"💸 <b>Amount:</b> ₹{amount}\n"
            f"📄 <b>Txn ID:</b> <code>{txn_id}</code>\n\n"
            "❗ Your payment was not approved in time.\n"
            "You can still use this token in our <b>Token Support Bot</b>."
        ),
        parse_mode="HTML",
        reply_markup=keyboard
    )
except Exception as e:
    print(f"❌ Could not notify user {user_id}: {e}")


# Notify admin/group (optional)

try:
    await bot.send_message(
        GROUP_ID,# Or use ADMIN_ID
        text=(
            f"📌 Token generated due to delay.\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"💰 Amount: ₹{amount}\n"
            f"🧾 Txn ID: <code>{txn_id}</code>\n"
            f"🔐 Token: <code>{token}</code>"
            ),
        parse_mode="HTML"
    )
except Exception as e:
    print(f"❌ Could not notify admin: {e}")
    await sleep(1)
                  # Repeat every minute
        
#-------------------------------------------------
# FastAPI for health check (Optional but useful for Azure/uptime monitors)
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "✅ Bot is alive and running!"}

# Bot setup
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

# Dispatcher setup
dp = Dispatcher(storage=MemoryStorage())

# Register all routers
def register_routers(dp: Dispatcher):
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(order_router)
    dp.include_router(my_orders_router)
    dp.include_router(wallet_router)
    dp.include_router(group_router)
    dp.include_router(contact_router)
    dp.include_router(admin_button_router)
   # dp.include_router(con_router)
    # dp.include_router(cancel_router)  # Uncomment if you moved cancel logic to a router

# Main function
async def main():
    # Start auto order updater loop
    asyncio.create_task(auto_update_orders())
    asyncio.create_task(auto_generate_tokens())


    # Initialize DB and logging
    initialize_database()
    logging.basicConfig(level=logging.INFO)
    logging.info("✅ Bot initialized successfully.")

    # Register routers
    register_routers(dp)

    # Remove webhook and start long polling
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("📡 Starting bot via long polling...")

    await dp.start_polling(bot)

# Entry point
if __name__ == "__main__":
    asyncio.run(main())
