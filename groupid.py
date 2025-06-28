import os
from dotenv import load_dotenv

load_dotenv()

GROUP_ID = os.getenv("GROUP_ID")
print(f"✅ GROUP_ID from .env: {GROUP_ID}")
