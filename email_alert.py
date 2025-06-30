# email_alert.py
import smtplib
from email.message import EmailMessage

def send_email_alert(username, txn_id, amount):
    msg = EmailMessage()
    msg.set_content(
        f"🧾 Balance Add Request\n\n"
        f"👤 User: @{username}\n"
        f"💳 Transaction ID: {txn_id}\n"
        f"💰 Amount: ₹{amount}\n"
        f"📌 Status: Pending"
    )
    msg["Subject"] = f"📢 New Balance Add Request - {username}"
    msg["From"] = "nishantbharadwaj13@gmail.com"
    msg["To"] = "nishantbhardwaj9799@gmail.com"

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login("nishantbharadwaj13@gmail.com", "ekbc mwgg lwal risu")
            smtp.send_message(msg)
        print("✅ Email sent successfully!")
    except Exception as e:
        print("❌ Failed to send email:", e)
