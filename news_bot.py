#!/usr/bin/env python3
"""NEXUS News Bot - NUR deine Lesezeichen-Quellen -> Telegram"""
import os, json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
MODE      = os.environ.get("MODE", "live")

# === NUR deine Lesezeichen-Quellen ===
# Quellen MIT RSS Feed
FEEDS = {
    # Krypto
    "CoinTelegraph":      ("https://cointelegraph.com/rss",                             "EN"),
    "CoinDesk":           ("https://www.coindesk.com/arc/outboundfeeds/rss/",           "EN"),
    "CryptoPanic":        ("https://cryptopanic.com/news/rss/",                          "EN"),
    "BTC-ECHO":           ("https://www.btc-echo.de/feed/",                             "DE"),
    # Maerkte & Wirtschaft
    "Reuters Business":   ("https://feeds.reuters.com/reuters/businessNews",            "EN"),
    "Reuters World":      ("https://feeds.reuters.com/reuters/worldNews",               "EN"),
    "Investing.com":      ("https://www.investing.com/rss/news.rss",                   "EN"),
    "Trading Economics":  ("https://tradingeconomics.com/rss",                          "EN"),
    "CFTC Press":         ("https://www.cftc.gov/rss/pressreleases.xml",               "EN"),
}

HIGH_KW = [
    # Krypto
    "bitcoin","btc","crypto","ethereum","etf","crash","hack","collapse","bankruptcy",
    "binance","coinbase","sec crypto","fed crypto","regulation",
    # Geopolitik
    "missile","attack","war","invasion","nuclear","sanctions","nato","coup",
    "north korea","iran","trump","putin","tariff","trade war",
    # Wirtschaft
    "fed rate","interest rate","federal reserve","ecb rate","recession","inflation",
    "oil price","market crash","rate hike","rate cut","gdp",
    # Deutsch
    "leitzins","zinsentscheidung","rezession","boersencrash","ezb","bundesbank",
    "krypto","bitcoin kurs",
    # Korea
    "kospi","kosdaq","samsung","hyundai","sk hynix","bank of korea",
]
MED_KW = [
    "earnings","unemployment","opec","g7","g20","imf","blockchain","defi","altcoin",
    "forex","dollar","euro","yen","gold","silver","oil","commodity",
]

def send_tg(text):
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true"
    }).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data, method="POST"), timeout=10)
        return True
    except Exception as e:
        print(f"TG error: {e}"); return False

def fetch_feed(name, url, lang="EN"):
    items = []
    try:
        root = ET.parse(urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=12)).getroot()
        ns = (root.tag.split("}")[0]+"}") if root.tag.startswith("{") else ""
        for item in root.iter(f"{ns}item"):
            title = (item.findtext(f"{ns}title") or "").strip()
            link  = (item.findtext(f"{ns}link")  or "").strip()
            pub   = item.findtext(f"{ns}pubDate") or ""
            try: pub_dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
            except: pub_dt = datetime.now(timezone.utc)
            items.append({"title": title, "link": link, "pub": pub_dt, "source": name, "lang": lang})
    except Exception as e:
        print(f"Feed [{name}]: {e}")
    return items

def score(t):
    t = t.lower()
    return sum(3 for k in HIGH_KW if k in t) + sum(1 for k in MED_KW if k in t)

def category(t):
    t = t.lower()
    if any(k in t for k in ["bitcoin","btc","crypto","ethereum","coin","defi","krypto","blockchain","binance","coinbase"]):
        return "KRYPTO / CRYPTO"
    if any(k in t for k in ["kospi","kosdaq","samsung","hyundai","korea","seoul"]):
        return "KOREA"
    if any(k in t for k in ["trump","white house","congress","tariff","trade war"]):
        return "USA / TRUMP"
    if any(k in t for k in ["fed","ecb","ezb","rate","zinsen","gdp","recession","inflation","oil","gold","forex","dollar"]):
        return "WIRTSCHAFT / ECONOMY"
    return "WELTPOLITIK / WORLD"

def run_live():
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=35)
    all_items = []
    for name, (url, lang) in FEEDS.items():
        all_items.extend(fetch_feed(name, url, lang))
    seen, fresh = set(), []
    for item in sorted(all_items, key=lambda x: x["pub"], reverse=True):
        if item["pub"] < cutoff: continue
        k = item["title"][:60].lower()
        if k in seen: continue
        seen.add(k); fresh.append(item)
    top = sorted([(score(i["title"]), i) for i in fresh], reverse=True)
    top = [(s, i) for s, i in top if s >= 3]
    sent = 0
    for sc, item in top[:5]:
        cat = category(item["title"])
        flag = "[DE]" if item["lang"] == "DE" else "[EN]"
        msg = (
            f"<b>BREAKING - {cat}</b>\n\n"
            f"{flag} {item['title']}\n\n"
            f"Quelle: <a href='{item['link']}'>{item['source']}</a>"
            f" - {item['pub'].strftime('%H:%M UTC')}"
        )
        if send_tg(msg): sent += 1; print(f"Sent [{item['source']}]: {item['title'][:60]}")
    print(f"Fertig: {sent} Nachrichten gesendet.")

def get_price(coin_id):
    try:
        with urllib.request.urlopen(
            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true",
            timeout=10) as r:
            d = json.load(r)
        return d[coin_id]["usd"], d[coin_id]["usd_24h_change"]
    except: return 0.0, 0.0

def run_summary():
    today   = datetime.now().strftime("%d.%m.%Y")
    now_str = datetime.now().strftime("%H:%M")
    bp, bc = get_price("bitcoin"); ep, ec = get_price("ethereum")
    btc = f"BTC: ${bp:,.0f} ({bc:+.1f}%)" if bp else "BTC: N/A"
    eth = f"ETH: ${ep:,.0f} ({ec:+.1f}%)" if ep else "ETH: N/A"
    all_items = []
    for name, (url, lang) in FEEDS.items():
        all_items.extend(fetch_feed(name, url, lang))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    today_items = [i for i in all_items if i["pub"] >= cutoff]
    world, crypto, korea, usa, eco = [], [], [], [], []
    for item in sorted(today_items, key=lambda x: score(x["title"]), reverse=True):
        cat = category(item["title"])
        flag = "[DE]" if item["lang"] == "DE" else "[EN]"
        e = f"{flag} {item['source']}: {item['title'][:100]}"
        if   cat == "KRYPTO / CRYPTO"       and len(crypto) < 3: crypto.append(e)
        elif cat == "KOREA"                  and len(korea)  < 2: korea.append(e)
        elif cat == "USA / TRUMP"            and len(usa)    < 3: usa.append(e)
        elif cat == "WIRTSCHAFT / ECONOMY"   and len(eco)    < 3: eco.append(e)
        elif cat == "WELTPOLITIK / WORLD"    and len(world)  < 3: world.append(e)
    def fmt(lst): return "\n".join(f"- {i}" for i in lst) if lst else "- Ruhiger Tag / Quiet day"
    msg = (
        f"<b>NEXUS TAGESABSCHLUSS - {today}</b>\n"
        f"========================\n\n"
        f"<b>KRYPTO / CRYPTO</b>\n{btc} | {eth}\n{fmt(crypto)}\n\n"
        f"<b>WIRTSCHAFT / ECONOMY</b>\n{fmt(eco)}\n\n"
        f"<b>WELTPOLITIK / WORLD</b>\n{fmt(world)}\n\n"
        f"<b>USA / TRUMP</b>\n{fmt(usa)}\n\n"
        f"<b>KOREA</b>\n{fmt(korea)}\n\n"
        f"Quellen: CoinTelegraph, CoinDesk, CryptoPanic, BTC-ECHO,\n"
        f"Reuters, Investing.com, Trading Economics, CFTC\n"
        f"[DE] = Deutsch | [EN] = English\n"
        f"========================\n"
        f"<i>NEXUS - {now_str} Uhr</i>"
    )
    send_tg(msg)
    print("Tagesabschluss gesendet.")

if __name__ == "__main__":
    run_summary() if MODE == "summary" else run_live()
