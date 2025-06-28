from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import requests
from config import ADMIN_ID, SMM_API_KEY, SMM_API_URL, GROUP_ID
from db import bot, cur, conn

router = Router()

@router.message(Command("update_orders"))
async def update_all_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ You are not authorized.")

    # Fetch all pending orders
    pending_orders = cur.execute(
        "SELECT order_id, user_id, price, status FROM orders WHERE status = 'pending'"
    ).fetchall()

    if not pending_orders:
        return await message.answer("✅ No pending orders to update.")

    updated_count = 0
    refund_count = 0

    for order_id, user_id, price, current_status in pending_orders:
        try:
            response = requests.post(SMM_API_URL, data={
                "key": SMM_API_KEY,
                "action": "status",
                "order": order_id
            })

            resp_json = response.json()
            new_status = resp_json.get("status")

            # Skip if no change
            if not new_status or new_status.lower() == current_status.lower():
                continue

            # Update DB
            cur.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
            conn.commit()
            updated_count += 1

            # If cancelled, refund and notify
            if new_status.lower() in ["canceled", "cancelled"]:
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
                conn.commit()
                refund_count += 1

                try:
                    await bot.send_message(
                        user_id,
                        f"❌ Your order `{order_id}` was *cancelled*.\n💰 ₹{price:.2f} has been refunded.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"❗ Couldn't notify user {user_id}: {e}")

                try:
                    await bot.send_message(
                        GROUP_ID,
                        f"🔁 *Refund Processed*\n👤 User: `{user_id}`\n🆔 Order: `{order_id}`\n💸 Amount: ₹{price:.2f}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"❗ Couldn't notify group: {e}")

            else:
                # Notify status update
                try:
                    await bot.send_message(
                        user_id,
                        f"📦 Your order `{order_id}` status has been updated to *{new_status}*.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"❗ Couldn't notify user {user_id}: {e}")

        except Exception as e:
            print(f"❌ Error updating order `{order_id}`:", e)

    await message.answer(
        f"✅ Orders Updated: {updated_count}\n💸 Refunds Processed: {refund_count}"
    )
