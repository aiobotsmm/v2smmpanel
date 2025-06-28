from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from db import cur, conn, bot
from config import ADMIN_IDS, GROUP_ID
from keyboards import main_menu

admin_router = Router()

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- Notify group helper ---
async def notify_group_payment(user_id: int, amount: float, reason: str = "Balance Update"):
    try:
        user = cur.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)).fetchone()
        name = user[0] if user else "Unknown"
        msg = (
            f"💸 *{reason}*\n"
            f"👤 User: `{user_id}` ({name})\n"
            f"💰 Amount: ₹{amount:.2f}"
        )
        await bot.send_message(GROUP_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"❗ Group notify failed: {e}")

# --- /addbalance ---
@admin_router.message(Command("addbalance"))
async def add_balance_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    parts = m.text.split()
    if len(parts) != 3:
        return await m.answer("Usage: /addbalance <user_id> <amount>")
    try:
        uid = int(parts[1])
        amt = float(parts[2])
    except ValueError:
        return await m.answer("❌ Invalid format.")
    user = cur.execute("SELECT balance FROM users WHERE user_id = ?", (uid,)).fetchone()
    if not user:
        return await m.answer("❌ User not found.")
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, uid))
    conn.commit()
    await m.answer(f"✅ ₹{amt:.2f} added to user {uid}")
    try:
        await bot.send_message(uid, f"✅ ₹{amt:.2f} has been added to your wallet by the admin.")
    except Exception as e:
        await m.answer(f"⚠️ Added, but couldn't notify user: {e}")
    await notify_group_payment(uid, amt, "🔧 Manual Balance Add")

# --- /deduct ---
@admin_router.message(Command("deduct"))
async def deduct_balance_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    parts = m.text.split()
    if len(parts) != 3:
        return await m.answer("Usage: /deduct <user_id> <amount>")
    try:
        uid = int(parts[1])
        amt = float(parts[2])
    except ValueError:
        return await m.answer("❌ Invalid format.")
    bal = cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    if not bal:
        return await m.answer("❌ User not found.")
    if bal[0] < amt:
        return await m.answer("❌ Insufficient balance.")
    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amt, uid))
    conn.commit()
    await m.answer(f"✅ ₹{amt:.2f} deducted from user {uid}")
    await bot.send_message(uid, f"⚠️ ₹{amt:.2f} was deducted from your wallet by the admin.")
    await notify_group_payment(uid, amt, "❌ Balance Deducted")

# --- /bonusadd ---
@admin_router.message(Command("bonusadd"))
async def add_bonus_command(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    try:
        parts = m.text.split()
        if len(parts) != 3:
            return await m.answer("❌ Usage: /bonusadd <user_id> <amount>")
        user_id = int(parts[1])
        bonus = float(parts[2])
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus, user_id))
        conn.commit()
        await m.answer(f"✅ ₹{bonus} bonus added to user `{user_id}`", parse_mode="Markdown")
        await bot.send_message(
            user_id,
            f"🤝 A bonus of ₹{bonus} was granted to your account by support. Thanks for using our panel."
        )
        await notify_group_payment(user_id, bonus, "🎁 Bonus Added")
    except Exception as e:
        await m.answer(f"⚠️ Error: {e}")

# --- /checkbalance ---
@admin_router.message(Command("checkbalance"))
async def check_balance_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    parts = m.text.split()
    if len(parts) != 2:
        return await m.answer("Usage: /checkbalance <user_id>")
    try:
        uid = int(parts[1])
    except ValueError:
        return await m.answer("❌ Invalid user ID.")
    row = cur.execute("SELECT balance FROM users WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        return await m.answer("❌ User not found.")
    bal = row[0]
    await m.answer(f"👤 User ID: {uid}\n💰 Balance: ₹{bal:.2f}")

# --- /userorders ---
@admin_router.message(Command("userorders"))
async def user_orders_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    parts = m.text.split()
    if len(parts) != 2:
        return await m.answer("Usage: /userorders <user_id>")
    try:
        uid = int(parts[1])
    except ValueError:
        return await m.answer("❌ Invalid user ID.")
    rows = cur.execute(
        "SELECT order_id, service_name, quantity, price, status FROM orders WHERE user_id=?",
        (uid,)
    ).fetchall()
    if not rows:
        return await m.answer("No orders found.")
    msg = f"📦 Order history for user {uid}:\n\n" + "\n\n".join(
        [f"#{r[0]} • {r[1]} x{r[2]} • ₹{r[3]:.2f} • {r[4]}" for r in rows])
    await m.answer(msg)

# --- /listusers ---
@admin_router.message(Command("listusers"))
async def list_users_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    rows = cur.execute("SELECT user_id, name, phone, balance FROM users").fetchall()
    if not rows:
        return await m.answer("No users found.")
    msg = "👥 Registered Users:\n\n" + "\n".join(
        [f"{r[0]} • {r[1]} • {r[2]} • ₹{r[3]:.2f}" for r in rows])
    await m.answer(msg)

# --- /stats ---
@admin_router.message(Command("stats"))
async def stats_cmd(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    total_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_orders = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    revenue = cur.execute("SELECT SUM(price) FROM orders").fetchone()[0] or 0.0
    revenue = round(float(revenue), 2)
    msg = (
        "📊 Bot Statistics:\n"
        f"• Total Users: {total_users}\n"
        f"• Total Orders: {total_orders}\n"
        f"• Total Revenue: ₹{revenue:.2f}"
    )
    await m.answer(msg)

# --- /refund ---
@admin_router.message(Command("refund"))
async def refund_by_order(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("❌ Unauthorized.")
    try:
        parts = m.text.split()
        if len(parts) != 2:
            return await m.answer("Usage: /refund <order_id>")
        order_id = parts[1]
        row = cur.execute("SELECT user_id, price FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return await m.answer("❌ Order not found.")
        user_id, amount = row
        cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        cur.execute("UPDATE orders SET status = 'refunded' WHERE order_id = ?", (order_id,))
        conn.commit()

        try:
            await bot.send_message(
                user_id, f"💸 Refund of ₹{amount:.2f} issued for Order `{order_id}`.",
                parse_mode="Markdown"
            )
        except: pass

        try:
            await bot.send_message(
                GROUP_ID,
                f"♻️ *Refund Issued*\n👤 User ID: `{user_id}`\n🆔 Order: `{order_id}`\n💰 Amount: ₹{amount:.2f}",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"❗ Group notify error: {e}")

        await m.answer("✅ Refund processed.")
    except Exception as e:
        await m.answer(f"❌ Failed: {e}")


