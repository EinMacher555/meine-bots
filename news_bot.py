#!/usr/bin/env python3
"""NEXUS News Bot - Telegram via GitHub Actions"""
import os, json, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
MODE      = os.environ.get("MODE", "live")

FEEDS_EN = {
    "Reuters World":    "https://feeds.reuters.com/reuters/worldNews",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "BBC World":        "http://feeds.bbci.co.uk/news/world/rss.xml",
    "CoinDesk":         "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph":    "https://cointelegraph.com/rss",
    "Al Jazeera":       "https://www.aljazeera.com/xml/rss/all.xml",
    "Yonhap EN":        "https://en.yna.co.kr/RSS/news.xml",
    "Korea Herald":     "https://www.koreaherald.com/common/rss_xml.php?ct=102",
}
FEEDS_DE = {
    "Tagesschau":   "https://www.tagesschau.de/xml/rss2/",
    "DW Deutsch":   "https://rss.dw.com/rdf/rss-de-all",
    "Spiegel":      "https://www.spiegel.de/schlagzeilen/index.rss",
    "Handelsblatt": "https://www.handelsblatt.com/rss09/politik.xml",
}
HKCM_CHANNEL_ID = "UC3AdN1bEmEonuSwXNS8LixQ"

HIGH_KW = [
    "missile","attack","explosion","war","invasion","nuclear","sanctions","nato",
    "coup","assassination","north korea","iran","trump","xi jinping","putin","tariff","trade war",
    "rakete","angriff","krieg","atomwaffen","sanktionen","putsch","attentat","nordkorea","handelskrieg",
    "bitcoin","btc","crypto","ethereum","etf","crash","hack","collapse","bankruptcy","binance",
    "fed rate","interest rate","federal reserve","ecb rate","recession","inflation",
    "oil price","market crash","rate hike","rate cut",
    "leitzins","zinsentscheidung","rezession","boersencrash","ezb","fed","bundesbank",
    "kospi","kosdaq","samsung","hyundai","sk hynix","bank of korea",
]
MED_KW = ["earnings","gdp","unemployment","opec","g7","g20","imf","blockchain","defi",
          "konjunktur","arbeitslosigkeit","bip","haushalt","schulden"]

def send_tg(text):
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true"}).encode()
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
            timeout=10)).getroot()
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

def fetch_youtube(channel_name, channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    items = []
    try:
        root = ET.parse(urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=10)).getroot()
        ns = "http://www.w3.org/2005/Atom"
        for entry in root.findall(f"{{{ns}}}entry"):
            title = (entry.findtext(f"{{{ns}}}title") or "").strip()
            link_el = entry.find(f"{{{ns}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
            pub_str = entry.findtext(f"{{{ns}}}published") or ""
            try: pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00")).astimezone(timezone.utc)
            except: pub_dt = datetime.now(timezone.utc)
            items.append({"title": title, "link": link, "pub": pub_dt, "source": channel_name, "lang": "DE"})
    except Exception as e:
        print(f"YouTube [{channel_name}]: {e}")
    return items

def score(t):
    t = t.lower()
    return sum(3 for k in HIGH_KW if k in t) + sum(1 for k in MED_KW if k in t)

def category(t):
    t = t.lower()
    if any(k in t for k in ["bitcoin","btc","crypto","ethereum","coin","defi","krypto","blockchain"]):
        return "&#8383;", "KRYPTO / CRYPTO"
    if any(k in t for k in ["kospi","kosdaq","samsung","hyundai","korea","yonhap","seoul"]):
        return "&#127472;&#127479;", "KOREA"
    if any(k in t for k in ["trump","white house","pentagon","congress"]):
        return "&#127482;&#127480;", "USA / TRUMP"
    if any(k in t for k in ["fed","ecb","ezb","rate","zinsen","gdp","bip","recession","rezession",
                              "inflation","oil","oel","gold","markt","market"]):
        return "&#128200;", "WIRTSCHAFT / ECONOMY"
    return "&#127758;", "WELTPOLITIK / WORLD"

def lang_flag(lang):
    return "&#127465;&#127466;" if lang == "DE" else "&#127468;&#127463;"

def get_price(coin_id):
    try:
        with urllib.request.urlopen(
            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true",
            timeout=10) as r:
            d = json.load(r)
        return d[coin_id]["usd"], d[coin_id]["usd_24h_change"]
    except: return 0.0, 0.0

def run_live():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=35)
    for item in fetch_youtube("HKCM", HKCM_CHANNEL_ID):
        if item["pub"] >= cutoff:
            msg = (f"<b>&#127916; HKCM - NEUES VIDEO</b>\n\n"
                   f"&#127465;&#127466; {item['title']}\n\n"
                   f"&#128279; <a href='{item['link']}'>Video ansehen</a> &#183; {item['pub'].strftime('%H:%M UTC')}")
            if send_tg(msg): print(f"HKCM: {item['title'][:60]}")
    all_items = []
    for n, u in FEEDS_EN.items(): all_items.extend(fetch_feed(n, u, "EN"))
    for n, u in FEEDS_DE.items(): all_items.extend(fetch_feed(n, u, "DE"))
    seen, fresh = set(), []
    for item in sorted(all_items, key=lambda x: x["pub"], reverse=True):
        if item["pub"] < cutoff: continue
        k = item["title"][:60].lower()
        if k in seen: continue
        seen.add(k); fresh.append(item)
    top = [(s,i) for s,i in sorted([(score(i["title"]),i) for i in fresh],reverse=True) if s >= 3]
    sent = 0
    for sc, item in top[:5]:
        em, cat = category(item["title"])
        flag = lang_flag(item["lang"])
        msg = (f"<b>&#128680; BREAKING</b> {em} {cat}\n\n"
               f"{flag} {item['title']}\n\n"
               f"&#128240; <a href='{item['link']}'>{item['source']}</a> &#183; {item['pub'].strftime('%H:%M UTC')}")
        if send_tg(msg): sent += 1
    print(f"Done: {sent} Breaking News gesendet.")

def run_morning():
    today = datetime.now().strftime("%d.%m.%Y")
    tag = {"Monday":"Montag","Tuesday":"Dienstag","Wednesday":"Mittwoch","Thursday":"Donnerstag",
           "Friday":"Freitag","Saturday":"Samstag","Sunday":"Sonntag"}.get(datetime.now().strftime("%A"), "")
    bp, bc = get_price("bitcoin"); ep, ec = get_price("ethereum")
    btc = f"BTC: ${bp:,.0f} ({bc:+.1f}%)" if bp else "BTC: N/A"
    eth = f"ETH: ${ep:,.0f} ({ec:+.1f}%)" if ep else "ETH: N/A"
    all_items = []
    for n, u in FEEDS_EN.items(): all_items.extend(fetch_feed(n, u, "EN"))
    for n, u in FEEDS_DE.items(): all_items.extend(fetch_feed(n, u, "DE"))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    items = [i for i in all_items if i["pub"] >= cutoff]
    world, crypto, korea, usa = [], [], [], []
    for item in sorted(items, key=lambda x: score(x["title"]), reverse=True):
        _, cat = category(item["title"])
        e = f"{lang_flag(item['lang'])} {item['title'][:110]}"
        if cat=="KRYPTO / CRYPTO" and len(crypto)<3: crypto.append(e)
        elif cat=="KOREA" and len(korea)<3: korea.append(e)
        elif cat=="USA / TRUMP" and len(usa)<3: usa.append(e)
        elif cat=="WELTPOLITIK / WORLD" and len(world)<3: world.append(e)
    def fmt(lst): return "\n".join(f"&#8226; {i}" for i in lst) if lst else "&#8226; Ruhige Nacht / Quiet night"
    msg = (f"&#9728;&#65039; <b>NEXUS MORGEN-BRIEFING</b> &#183; {tag}, {today}\n"
           f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n\n"
           f"&#8383; <b>KRYPTO</b>\n{btc} &#124; {eth}\n{fmt(crypto)}\n\n"
           f"&#127758; <b>WELTPOLITIK / WORLD</b>\n{fmt(world)}\n\n"
           f"&#127472;&#127479; <b>KOREA</b>\n{fmt(korea)}\n\n"
           f"&#127482;&#127480; <b>USA / TRUMP</b>\n{fmt(usa)}\n\n"
           f"&#127465;&#127466;=DE &#124; &#127468;&#127463;=EN\n&#9472;&#9472;&#9472;&#9472;\n"
           f"<i>Guten Morgen, Sinuk! &#128522;</i>")
    send_tg(msg); print("Morgen-Briefing gesendet.")

def run_summary():
    today = datetime.now().strftime("%d.%m.%Y")
    now_str = datetime.now().strftime("%H:%M")
    bp, bc = get_price("bitcoin"); ep, ec = get_price("ethereum")
    btc = f"BTC: ${bp:,.0f} ({bc:+.1f}%)" if bp else "BTC: N/A"
    eth = f"ETH: ${ep:,.0f} ({ec:+.1f}%)" if ep else "ETH: N/A"
    all_items = []
    for n, u in FEEDS_EN.items(): all_items.extend(fetch_feed(n, u, "EN"))
    for n, u in FEEDS_DE.items(): all_items.extend(fetch_feed(n, u, "DE"))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    items = [i for i in all_items if i["pub"] >= cutoff]
    world, crypto, korea, usa = [], [], [], []
    for item in sorted(items, key=lambda x: score(x["title"]), reverse=True):
        _, cat = category(item["title"])
        e = f"{lang_flag(item['lang'])} {item['title'][:110]}"
        if cat=="KRYPTO / CRYPTO" and len(crypto)<3: crypto.append(e)
        elif cat=="KOREA" and len(korea)<3: korea.append(e)
        elif cat=="USA / TRUMP" and len(usa)<3: usa.append(e)
        elif cat=="WELTPOLITIK / WORLD" and len(world)<3: world.append(e)
    def fmt(lst): return "\n".join(f"&#8226; {i}" for i in lst) if lst else "&#8226; Ruhiger Tag / Quiet day"
    msg = (f"&#127769; <b>NEXUS TAGESABSCHLUSS / DAILY CLOSE</b> &#8212; {today}\n"
           f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n\n"
           f"&#8383; <b>KRYPTO</b>\n{btc} &#124; {eth}\n{fmt(crypto)}\n\n"
           f"&#127758; <b>WELTPOLITIK / WORLD</b>\n{fmt(world)}\n\n"
           f"&#127472;&#127479; <b>KOREA</b>\n{fmt(korea)}\n\n"
           f"&#127482;&#127480; <b>USA / TRUMP</b>\n{fmt(usa)}\n\n"
           f"&#127465;&#127466;=DE &#124; &#127468;&#127463;=EN\n&#9472;&#9472;&#9472;&#9472;\n"
           f"<i>NEXUS &#183; {now_str} Uhr</i>")
    send_tg(msg); print("Tagesabschluss gesendet.")

if __name__ == "__main__":
    if   MODE == "summary": run_summary()
    elif MODE == "morning": run_morning()
    else:                   run_live()
