#!/usr/bin/env python3
"""NEXUS News Bot - Breaking News -> Telegram via GitHub Actions"""
import os, json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
MODE      = os.environ.get("MODE", "live")

FEEDS = {
    "Reuters World":    "https://feeds.reuters.com/reuters/worldNews",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "BBC World":        "http://feeds.bbci.co.uk/news/world/rss.xml",
    "CoinDesk":         "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph":    "https://cointelegraph.com/rss",
    "Korea Herald":     "https://www.koreaherald.com/common/rss_xml.php?ct=102",
    "Yonhap":           "https://en.yna.co.kr/RSS/news.xml",
    "Al Jazeera":       "https://www.aljazeera.com/xml/rss/all.xml",
}
HIGH_KW = [
    "missile","attack","explosion","war","invasion","nuclear","sanctions","nato",
    "coup","assassination","bitcoin","btc","crypto","ethereum","etf","crash",
    "hack","collapse","bankruptcy","fed rate","interest rate","federal reserve",
    "ecb rate","recession","inflation","oil price","market crash",
    "trump","xi jinping","putin","north korea","iran","tariff","trade war",
    "kospi","kosdaq","samsung","hyundai","sk hynix","bank of korea",
]
MED_KW = ["earnings","gdp","unemployment","opec","g7","g20","imf","blockchain","defi"]

def send_tg(text):
    data = urllib.parse.urlencode({"chat_id":CHAT_ID,"text":text,"parse_mode":"HTML","disable_web_page_preview":"true"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",data=data,method="POST"),timeout=10)
        return True
    except Exception as e: print(f"TG error: {e}"); return False

def fetch_feed(name, url):
    items = []
    try:
        root = ET.parse(urllib.request.urlopen(
            urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=10)).getroot()
        ns = (root.tag.split("}")[0]+"}") if root.tag.startswith("{") else ""
        for item in root.iter(f"{ns}item"):
            title = (item.findtext(f"{ns}title") or "").strip()
            link  = (item.findtext(f"{ns}link")  or "").strip()
            pub   = item.findtext(f"{ns}pubDate") or ""
            try: pub_dt = parsedate_to_datetime(pub).astimezone(timezone.utc)
            except: pub_dt = datetime.now(timezone.utc)
            items.append({"title":title,"link":link,"pub":pub_dt,"source":name})
    except Exception as e: print(f"Feed [{name}]: {e}")
    return items

def score(t):
    t=t.lower()
    return sum(3 for k in HIGH_KW if k in t)+sum(1 for k in MED_KW if k in t)

def category(t):
    t=t.lower()
    if any(k in t for k in ["bitcoin","btc","crypto","ethereum","coin","defi"]): return "&#8383;","KRYPTO"
    if any(k in t for k in ["kospi","kosdaq","samsung","hyundai","korea","yonhap","seoul"]): return "&#127472;&#127479;","KOREA"
    if any(k in t for k in ["trump","white house","pentagon","congress"]): return "&#127482;&#127480;","USA"
    if any(k in t for k in ["fed","ecb","rate","gdp","recession","inflation","oil","gold"]): return "&#128200;","WIRTSCHAFT"
    return "&#127758;","WELTPOLITIK"

def run_live():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=35)
    all_items = []
    for n, u in FEEDS.items(): all_items.extend(fetch_feed(n, u))
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
        em, cat = category(item["title"])
        msg = (f"<b>&#128680; BREAKING</b> {em} {cat}\n\n"
               f"{item['title']}\n\n"
               f"&#128240; <a href='{item['link']}'>{item['source']}</a> &#183; {item['pub'].strftime('%H:%M UTC')}")
        if send_tg(msg): sent += 1; print(f"Sent: {item['title'][:60]}")
    print(f"Done: {sent} gesendet.")

def get_price(coin_id):
    try:
        with urllib.request.urlopen(
            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true",timeout=10) as r:
            d = json.load(r)
        return d[coin_id]["usd"], d[coin_id]["usd_24h_change"]
    except: return 0.0, 0.0

def run_summary():
    today = datetime.now().strftime("%d.%m.%Y")
    now_str = datetime.now().strftime("%H:%M")
    bp, bc = get_price("bitcoin"); ep, ec = get_price("ethereum")
    btc = f"BTC: ${bp:,.0f} ({bc:+.1f}%)" if bp else "BTC: N/A"
    eth = f"ETH: ${ep:,.0f} ({ec:+.1f}%)" if ep else "ETH: N/A"
    all_items = []
    for n, u in FEEDS.items(): all_items.extend(fetch_feed(n, u))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    today_items = [i for i in all_items if i["pub"] >= cutoff]
    world, crypto, korea, usa = [], [], [], []
    for item in sorted(today_items, key=lambda x: score(x["title"]), reverse=True):
        _, cat = category(item["title"])
        if cat=="KRYPTO" and len(crypto)<3: crypto.append(item["title"])
        elif cat=="KOREA" and len(korea)<3:  korea.append(item["title"])
        elif cat=="USA"   and len(usa)<3:    usa.append(item["title"])
        elif cat=="WELTPOLITIK" and len(world)<3: world.append(item["title"])
    def fmt(lst): return "\n".join(f"&#8226; {i[:120]}" for i in lst) if lst else "&#8226; Ruhiger Tag"
    msg = (f"&#127769; <b>NEXUS TAGESABSCHLUSS</b> &#8212; {today}\n"
           f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n\n"
           f"&#8383; <b>KRYPTO</b>\n{btc} &#124; {eth}\n{fmt(crypto)}\n\n"
           f"&#127758; <b>WELTPOLITIK</b>\n{fmt(world)}\n\n"
           f"&#127472;&#127479; <b>KOREA</b>\n{fmt(korea)}\n\n"
           f"&#127482;&#127480; <b>USA / TRUMP</b>\n{fmt(usa)}\n\n"
           f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n"
           f"<i>NEXUS &#183; {now_str} Uhr</i>")
    send_tg(msg); print("Tagesabschluss gesendet.")

if __name__ == "__main__":
    run_summary() if MODE == "summary" else run_live()
