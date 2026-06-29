#!/usr/bin/env python3
"""NEXUS News Bot - Breaking News auf Englisch & Deutsch -> Telegram via GitHub Actions"""
import os, json, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
MODE      = os.environ.get("MODE", "live")

# HKCM Sitemap (oeffentlich, kein Login noetig)
HKCM_SITEMAP   = "https://hkcmanagement.de/sitemaps/sitemap-1.xml"
HKCM_SEEN_FILE = "hkcm_seen.json"

# Englische Quellen
FEEDS_EN = {
    "Reuters":          "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    "BBC World":        "http://feeds.bbci.co.uk/news/world/rss.xml",
    "CoinDesk":         "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph":    "https://cointelegraph.com/rss",
    "Al Jazeera":       "https://www.aljazeera.com/xml/rss/all.xml",
    "Yonhap EN":        "https://en.yna.co.kr/RSS/news.xml",
    "Yonhap Economy":   "https://en.yna.co.kr/RSS/economy.xml",
}
# Deutsche Quellen
FEEDS_DE = {
    "Tagesschau":       "https://www.tagesschau.de/xml/rss2/",
    "DW Deutsch":       "https://rss.dw.com/rdf/rss-de-all",
    "FAZ":              "https://www.faz.net/rss/aktuell/",
    "Handelsblatt":     "https://www.handelsblatt.com/contentexport/feed/schlagzeilen",
    "BTC Echo":         "https://www.btc-echo.de/feed/",
    "BeInCrypto":       "https://de.beincrypto.com/feed/",
}

HIGH_KW = [
    # Geopolitik EN
    "missile","attack","explosion","war","invasion","nuclear","sanctions","nato",
    "coup","assassination","north korea","iran","trump","xi jinping","putin","tariff","trade war",
    # Geopolitik DE
    "rakete","angriff","explosion","krieg","invasion","atomwaffen","sanktionen","putsch",
    "attentat","nordkorea","handelskrieg","zölle",
    # Bitcoin/Krypto
    "bitcoin","btc","crypto","ethereum","etf","crash","hack","collapse","bankruptcy","binance",
    # Wirtschaft EN
    "fed rate","interest rate","federal reserve","ecb rate","recession","inflation",
    "oil price","market crash","rate hike","rate cut",
    # Wirtschaft DE
    "leitzins","zinsentscheidung","rezession","inflation","ölpreis","börsencrash",
    "ezb","fed","bundesbank",
    # Korea
    "kospi","kosdaq","samsung","hyundai","sk hynix","bank of korea",
]
MED_KW = [
    "earnings","gdp","unemployment","opec","g7","g20","imf","blockchain","defi",
    "konjunktur","arbeitslosigkeit","bip","haushalt","schulden",
]

def send_tg(text):
    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true"
    }).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(
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

# ---- US-Wirtschaftskalender (nur USA, freie Quelle, gleiche Daten wie investing.com) ----

def get_us_econ():
    """Anstehende US-Wirtschaftstermine: Inflation, Leitzins, BIP/GDP, CPI, PPI, Arbeitslosen, Retail Sales."""
    KW = ["cpi", "ppi", "gdp", "federal funds", "fomc", "unemployment",
          "non-farm", "nonfarm", "retail sales", "inflation", "jobless",
          "average hourly earnings"]
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    try:
        req = urllib.request.Request(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
    except Exception as e:
        print(f"Econ error: {e}")
        return []
    now = datetime.now(timezone.utc)
    out = []
    for ev in data:
        if ev.get("country") != "USD":
            continue
        title = ev.get("title", "")
        if not any(k in title.lower() for k in KW):
            continue
        try:
            dt = datetime.fromisoformat(ev["date"]).astimezone(timezone.utc)
        except Exception:
            continue
        if dt < now - timedelta(hours=6):
            continue
        fc = esc(ev.get("forecast") or "-")
        pv = esc(ev.get("previous") or "-")
        out.append((dt, esc(title), fc, pv))
    out.sort(key=lambda x: x[0])
    return out[:8]

# ---- HKCM Artikel-Tracker (Sitemap-basiert) ----

def load_hkcm_seen():
    try:
        with open(HKCM_SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_hkcm_seen(slugs):
    seen_list = sorted(slugs)
    if len(seen_list) > 500:
        seen_list = seen_list[-500:]
    with open(HKCM_SEEN_FILE, "w") as f:
        json.dump(seen_list, f)

def get_hkcm_title(url, slug):
    """Artikel-URL aufrufen und <title>-Tag extrahieren"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read(8192).decode("utf-8", errors="ignore")
        m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception as e:
        print(f"HKCM title [{slug}]: {e}")
    return " ".join(w.capitalize() for w in slug.replace("-", " ").split())

def check_hkcm():
    """Neue HKCM-Artikel via Sitemap pruefen und per Telegram benachrichtigen"""
    try:
        req = urllib.request.Request(
            HKCM_SITEMAP, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            xml_text = r.read().decode("utf-8")
    except Exception as e:
        print(f"HKCM sitemap error: {e}"); return

    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=35)

    pattern = re.compile(
        r"<loc>(https://hkcmanagement\.de/hkcmnews/([^<]+))</loc>\s*<lastmod>([^<]+)</lastmod>"
    )

    seen     = load_hkcm_seen()
    new_seen = set(seen)
    sent     = 0

    for m in pattern.finditer(xml_text):
        url, slug, lastmod_str = m.group(1), m.group(2), m.group(3)

        if slug in seen:
            continue

        try:
            lastmod = datetime.fromisoformat(lastmod_str).astimezone(timezone.utc)
        except:
            continue

        if lastmod < cutoff:
            continue

        title = get_hkcm_title(url, slug)

        msg = (
            f"<b>&#128240; HKCM – NEUER ARTIKEL</b>\n\n"
            f"&#127465;&#127466; {title}\n\n"
            f"&#128279; <a href='{url}'>&#128214; Jetzt lesen</a>"
            f"  &#183;  {lastmod.strftime('%H:%M')} Uhr"
        )
        if send_tg(msg):
            sent += 1
            print(f"HKCM: {title[:60]}")
        new_seen.add(slug)

    if new_seen != seen:
        save_hkcm_seen(new_seen)
        print(f"HKCM seen-Datei aktualisiert ({len(new_seen)} Eintraege)")

    print(f"HKCM: {sent} neue Artikel gesendet.")

# ---- Breaking News ----

def run_live():
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=35)

    check_hkcm()

    all_items = []
    for n, u in FEEDS_EN.items(): all_items.extend(fetch_feed(n, u, "EN"))
    for n, u in FEEDS_DE.items(): all_items.extend(fetch_feed(n, u, "DE"))

    seen, fresh = set(), []
    for item in sorted(all_items, key=lambda x: x["pub"], reverse=True):
        if item["pub"] < cutoff: continue
        k = item["title"][:60].lower()
        if k in seen: continue
        seen.add(k); fresh.append(item)

    top = sorted([(score(i["title"]), i) for i in fresh], key=lambda x: x[0], reverse=True)
    top = [(s, i) for s, i in top if s >= 3]
    sent = 0
    for sc, item in top[:5]:
        em, cat = category(item["title"])
        flag = lang_flag(item["lang"])
        msg = (
            f"<b>&#128680; BREAKING</b> {em} {cat}\n\n"
            f"{flag} {item['title']}\n\n"
            f"&#128240; <a href='{item['link']}'>{item['source']}</a> "
            f"&#183; {item['pub'].strftime('%H:%M UTC')}"
        )
        if send_tg(msg): sent += 1; print(f"Sent: {item['title'][:60]}")
    print(f"Done: {sent} Breaking News gesendet.")

# ---- Preise ----

def get_price(coin_id):
    try:
        with urllib.request.urlopen(
            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true",
            timeout=10) as r:
            d = json.load(r)
        return d[coin_id]["usd"], d[coin_id]["usd_24h_change"]
    except: return 0.0, 0.0

# ---- Morgen-Briefing ----

def run_morning():
    """Morgen-Briefing um 08:00 CEST - letzte 12 Stunden"""
    today   = datetime.now().strftime("%d.%m.%Y")
    weekday = datetime.now().strftime("%A")
    de_days = {
        "Monday":"Montag","Tuesday":"Dienstag","Wednesday":"Mittwoch",
        "Thursday":"Donnerstag","Friday":"Freitag","Saturday":"Samstag","Sunday":"Sonntag"
    }
    tag = de_days.get(weekday, weekday)

    bp, bc = get_price("bitcoin")
    ep, ec = get_price("ethereum")
    btc = f"BTC: ${bp:,.0f} ({bc:+.1f}%)" if bp else "BTC: N/A"
    eth = f"ETH: ${ep:,.0f} ({ec:+.1f}%)" if ep else "ETH: N/A"

    all_items = []
    for n, u in FEEDS_EN.items(): all_items.extend(fetch_feed(n, u, "EN"))
    for n, u in FEEDS_DE.items(): all_items.extend(fetch_feed(n, u, "DE"))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    morning_items = [i for i in all_items if i["pub"] >= cutoff]

    world, crypto, korea, usa = [], [], [], []
    for item in sorted(morning_items, key=lambda x: score(x["title"]), reverse=True):
        _, cat = category(item["title"])
        flag = lang_flag(item["lang"])
        entry = f"{flag} {item['title'][:110]}"
        if cat == "KRYPTO / CRYPTO"       and len(crypto) < 3: crypto.append(entry)
        elif cat == "KOREA"               and len(korea)  < 3: korea.append(entry)
        elif cat == "USA / TRUMP"         and len(usa)    < 3: usa.append(entry)
        elif cat == "WELTPOLITIK / WORLD" and len(world)  < 3: world.append(entry)

    def fmt(lst): return "\n".join(f"&#8226; {i}" for i in lst) if lst else "&#8226; Ruhige Nacht / Quiet night"

    econ = get_us_econ()
    def fmt_econ(evs):
        if not evs: return "&#8226; Keine relevanten US-Termine diese Woche"
        out = []
        for dt, t, fc, pv in evs:
            out.append(f"&#8226; {dt.strftime('%d.%m %H:%M')} UTC &#183; {t}  (Prog: {fc} | Vor: {pv})")
        return "\n".join(out)

    msg = (
        f"&#9728;&#65039; <b>NEXUS MORGEN-BRIEFING</b> &#183; {tag}, {today}\n"
        f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n\n"
        f"&#8383; <b>KRYPTO / CRYPTO</b>\n{btc} &#124; {eth}\n{fmt(crypto)}\n\n"
        f"&#127758; <b>WELTPOLITIK / WORLD POLITICS</b>\n{fmt(world)}\n\n"
        f"&#127472;&#127479; <b>KOREA</b>\n{fmt(korea)}\n\n"
        f"&#127482;&#127480; <b>USA / TRUMP</b>\n{fmt(usa)}\n\n"
        f"&#128197; <b>US-WIRTSCHAFTSKALENDER</b>\n{fmt_econ(econ)}\n\n"
        f"&#127465;&#127466; = Deutsch &#124; &#127468;&#127463; = English\n"
        f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n"
        f"<i>Guten Morgen, Sinuk! &#128522; &#183; NEXUS</i>"
    )
    send_tg(msg)
    print("Morgen-Briefing gesendet.")

# ---- Tagesabschluss ----

def run_summary():
    today   = (datetime.strptime(os.environ["OVERRIDE_DATE"], "%Y-%m-%d") if os.environ.get("OVERRIDE_DATE") else datetime.now()).strftime("%d.%m.%Y")
    now_str = datetime.now().strftime("%H:%M")

    bp, bc = get_price("bitcoin")
    ep, ec = get_price("ethereum")
    btc = f"BTC: ${bp:,.0f} ({bc:+.1f}%)" if bp else "BTC: N/A"
    eth = f"ETH: ${ep:,.0f} ({ec:+.1f}%)" if ep else "ETH: N/A"

    all_items = []
    for n, u in FEEDS_EN.items(): all_items.extend(fetch_feed(n, u, "EN"))
    for n, u in FEEDS_DE.items(): all_items.extend(fetch_feed(n, u, "DE"))

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    today_items = [i for i in all_items if i["pub"] >= cutoff]

    world, crypto, korea, usa = [], [], [], []
    for item in sorted(today_items, key=lambda x: score(x["title"]), reverse=True):
        _, cat = category(item["title"])
        flag = lang_flag(item["lang"])
        entry = f"{flag} {item['title'][:110]}"
        if cat == "KRYPTO / CRYPTO"       and len(crypto) < 3: crypto.append(entry)
        elif cat == "KOREA"               and len(korea)  < 3: korea.append(entry)
        elif cat == "USA / TRUMP"         and len(usa)    < 3: usa.append(entry)
        elif cat == "WELTPOLITIK / WORLD" and len(world)  < 3: world.append(entry)

    def fmt(lst): return "\n".join(f"&#8226; {i}" for i in lst) if lst else "&#8226; Ruhiger Tag / Quiet day"

    msg = (
        f"&#127769; <b>NEXUS TAGESABSCHLUSS / DAILY CLOSE</b> &#8212; {today}\n"
        f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n\n"
        f"&#8383; <b>KRYPTO / CRYPTO</b>\n{btc} &#124; {eth}\n{fmt(crypto)}\n\n"
        f"&#127758; <b>WELTPOLITIK / WORLD POLITICS</b>\n{fmt(world)}\n\n"
        f"&#127472;&#127479; <b>KOREA</b>\n{fmt(korea)}\n\n"
        f"&#127482;&#127480; <b>USA / TRUMP</b>\n{fmt(usa)}\n\n"
        f"&#127465;&#127466; = Deutsch &#124; &#127468;&#127463; = English\n"
        f"&#9472;&#9472;&#9472;&#9472;&#9472;&#9472;\n"
        f"<i>NEXUS &#183; {now_str} Uhr</i>"
    )
    send_tg(msg)
    print("Tagesabschluss gesendet.")

# ---- Entry Point ----

if __name__ == "__main__":
    if   MODE == "summary": run_summary()
    elif MODE == "morning": run_morning()
    else:                   run_live()
