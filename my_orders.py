from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from db import cur

router = Router()

@router.message(F.text == "📄 My Orders")
async def view_orders(message: Message):
    try:
        rows = cur.execute(
            "SELECT order_id, service_name, quantity, price, status FROM orders WHERE user_id=?",
            (message.from_user.id,)
        ).fetchall()

        if not rows:
            return await message.answer(
                "📦 <b>No Orders Found</b>\n\n"
                "😕 Looks like you haven’t placed any orders yet.\n"
                "🚀 Start your journey by tapping on <b>New Order</b> and explore our services!",
                parse_mode="HTML"
            )


        orders = []
        for r in rows:
            orders.append(
                f"🆔 *Order ID:* `{r[0]}`\n"
                f"📦 *Service:* {r[1]}\n"
                f"🔢 *Qty:* {r[2]}\n"
                f"💰 *Cost:* ₹{r[3]:.2f}\n"
                f"📊 *Status:* `{r[4]}`"
            )

        msg = "📦 *Your Orders:*\n\n" + "\n\n".join(orders)
        msg += "\n\n❗ *You can cancel any ongoing operation anytime by typing* `/cancel`."

        await message.answer(msg, parse_mode="Markdown")

    except Exception as e:
        await message.answer("⚠️ Failed to fetch orders. Please try again later.")
        print(f"[view_orders ERROR] {e}")
