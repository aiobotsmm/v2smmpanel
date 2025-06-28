from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import ADMIN_IDS

# ✅ Helper: check if user is admin
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ✅ Main user menu with optional "Admin Panel" button
def main_menu(user_id: int):
    buttons = [
        [KeyboardButton(text="💰 My Wallet"), KeyboardButton(text="💰 Add Balance")],
        [KeyboardButton(text="📦 New Order"), KeyboardButton(text="📄 My Orders")],
        [KeyboardButton(text="📞 Contact Admin")]
    ]
    
    if is_admin(user_id):
        buttons.append([KeyboardButton(text="👮 Admin Panel")])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ✅ Inline UPI confirmation button
def upi_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ I Paid", callback_data="paid_done")]
        ]
    )

# ✅ Inline Admin control panel
def admin_panel_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Admin", callback_data="add_admin")],
            [InlineKeyboardButton(text="🚫 Remove Admin", callback_data="remove_admin")]
        ]
    )
