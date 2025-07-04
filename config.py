import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN="7542766614:AAHHD2bZZu4dMBsm55Nfq4T-y_IsJfeFTnY"
GROUP_ID = int(os.getenv("GROUP_ID"))

# ✅ Multi-admin support (comma-separated in .env)
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

SMM_API_KEY = os.getenv("SMM_API_KEY")
SMM_API_URL = os.getenv("SMM_API_URL")
UPI_ID = os.getenv("UPI_ID")

# ✅ Optional support username config (used in admin_contact.py)
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "sastasmmhelper_bot")
