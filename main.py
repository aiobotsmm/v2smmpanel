# main.py

import asyncio
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import API_TOKEN
from db import conn, cur, initialize_database

# Routers
from user_routes import router as user_router
from admin import admin_router
from order import router as order_router
from my_orders import router as my_orders_router
from wallet_balance import router as wallet_router
from orderupdate import router as order_update_router
from groupdata import router as group_router
from admin_contact import contact_router
# from cancel import cancel_router  # Optional: if needed

# Keyboards (if needed globally)
from keyboards import main_menu, upi_keyboard

# FastAPI health check app (optional but nice)
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "🤖 Bot is alive"}

# Bot setup
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

# Dispatcher setup
dp = Dispatcher(storage=MemoryStorage())

# Function to register all routers
def register_routers(dp: Dispatcher):
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(order_router)
    dp.include_router(my_orders_router)
    dp.include_router(wallet_router)
    dp.include_router(order_update_router)
    dp.include_router(group_router)
    dp.include_router(contact_router)
    # dp.include_router(cancel_router)  # Uncomment if implemented

# Main async function
async def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("✅ Initializing bot...")

    initialize_database()
    register_routers(dp)

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🤖 Bot is starting via long polling...")

    await dp.start_polling(bot)

# Entry point
if __name__ == "__main__":
    asyncio.run(main())
