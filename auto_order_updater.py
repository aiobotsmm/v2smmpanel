# auto_order_updater.py
import asyncio
import requests
from config import SMM_API_KEY, SMM_API_URL, GROUP_ID
from db import bot, cur, conn

async def auto_update_orders():
    while True:
        try:
            pending_orders = cur.execute(
                "SELECT order_id, user_id, price, status FROM orders WHERE status = 'pending'"
            ).fetchall()

            for order_id, user_id, price, current_status in pending_orders:
                try:
                    resp = requests.post(SMM_API_URL, data={
                        "key": SMM_API_KEY,
                        "action": "status",
                        "order": order_id
                    }).json()

                    new_status = resp.get("status")

                    if not new_status or new_status.lower() == current_status.lower():
                        continue

                    # Update DB
                    cur.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
                    conn.commit()

                    if new_status.lower() in ["canceled", "cancelled"]:
                        # Refund if canceled
                        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
                        conn.commit()

                        await bot.send_message(
                            user_id,
                            f"❌ Order `{order_id}` was *cancelled*. ₹{price:.2f} refunded.",
                            parse_mode="Markdown"
                        )
                        await bot.send_message(
                            GROUP_ID,
                            f"🔁 *Refunded Order*\n👤 `{user_id}`\n🆔 `{order_id}`\n💰 ₹{price:.2f}",
                            parse_mode="Markdown"
                        )

                    elif new_status.lower() == "completed":
                        await bot.send_message(
                            user_id,
                            f"✅ Your order `{order_id}` is *completed* successfully!",
                            parse_mode="Markdown"
                        )

                except Exception as e:
                    print(f"❗ Failed updating order {order_id}: {e}")

        except Exception as e:
            print("❗ Auto updater failed:", e)

        await asyncio.sleep(60)  # Wait 60 seconds before next run
