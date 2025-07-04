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
#from admin import router as admin_router
# from cancel import cancel_router  # Optional if you separate cancel handler

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
   # dp.include_router(admin_router)
    # dp.include_router(cancel_router)  # Uncomment if you moved cancel logic to a router

# Main function
async def main():
    # Start auto order updater loop
    asyncio.create_task(auto_update_orders())

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
