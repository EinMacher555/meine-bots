# Was tut das? → Holt aktuelle News und schickt sie per Telegram
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Was tut das? → Holt Top-News von NewsAPI
def hole_news():
    # Kostenloser News-Service ohne API-Key
    url = "https://rss.dw.com/rdf/rss-en-bus"
    response = requests.get(url)
    
    nachrichten = []
    
    # XML parsen
    import re
    titles = re.findall(r'<title>(.*?)</title>', response.text)
    
    # Erste 5 Nachrichten nehmen
    for title in titles[1:6]:  # erste überspringen (Feed-Titel)
        nachrichten.append(f"📰 {title}")
    
    return nachrichten

# Was tut das? → Schickt Nachricht per Telegram
def sende_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, json=payload)

# Hauptprogramm
print("🔍 Hole aktuelle News...")
news = hole_news()

nachricht = "📊 DEIN TÄGLICHES BRIEFING\n"
nachricht += "━━━━━━━━━━━━━━━\n\n"
nachricht += "🌍 WIRTSCHAFT & MÄRKTE:\n\n"

for artikel in news:
    nachricht += f"{artikel}\n"

nachricht += "\n━━━━━━━━━━━━━━━"
nachricht += "\n🤖 EinKoreaner's News-Agent"

sende_telegram(nachricht)
print("✅ News gesendet! Schau auf dein Handy!")