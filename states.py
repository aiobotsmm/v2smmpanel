# states.py
from aiogram.fsm.state import StatesGroup, State

# 🚀 Registration Flow
class Register(StatesGroup):
    name = State()
    phone = State()

# 💰 Add Balance Flow
class AddBalance(StatesGroup):
    amount = State()
    txn_id = State()

# 📦 Order Placement Flow
class PlaceOrder(StatesGroup):
    svc_id = State()
    svc_name = State()
    svc_rate = State()
    svc_link = State()
    svc_qty = State()
