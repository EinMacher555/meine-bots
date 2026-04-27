# Was tut das? → Zeigt deine Chat ID automatisch
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
r = requests.get(url)
data = r.json()

if data["result"]:
    chat_id = data["result"][0]["message"]["chat"]["id"]
    print(f"✅ Deine Chat ID ist: {chat_id}")
else:
    print("❌ Keine Nachrichten gefunden!")
    print("→ Schreib deinem Bot /start und versuche es nochmal!")