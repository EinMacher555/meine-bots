
import os
import requests
from dotenv import load_dotenv

# .env Datei laden
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
payload = {"chat_id": CHAT_ID, "text": "🚀 EinKoreaner's Bot läuft! GitHub Setup komplett!"}

response = requests.post(url, json=payload)

if response.status_code == 200:
    print("✅ Nachricht gesendet! Schau auf dein Handy!")
else:
    print(f"❌ Fehler: {response.status_code}")
    print(response.json())