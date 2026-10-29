"""Lecture des flux RSS fondamentaux (banques centrales, stats US, énergie)."""

import time
from datetime import datetime, timezone

import feedparser

# User-Agent explicite : certains sites (BLS notamment) refusent les requêtes sans
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) macrofx-bot/1.0"

# nom court -> infos de la source
SOURCES = {
    "fed": {
        "name": "Federal Reserve",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "currencies": ["USD"],
        "color": 0x1F4E79,
    },
    "fed-speeches": {
        "name": "Fed - discours",
        "url": "https://www.federalreserve.gov/feeds/speeches.xml",
        "currencies": ["USD"],
        "color": 0x1F4E79,
    },
    "ecb": {
        "name": "BCE",
        "url": "https://www.ecb.europa.eu/rss/press.html",
        "currencies": ["EUR"],
        "color": 0x003399,
    },
    "boe": {
        "name": "Bank of England",
        "url": "https://www.bankofengland.co.uk/rss/news",
        "currencies": ["GBP"],
        "color": 0x8B0000,
    },
    "boj": {
        "name": "Bank of Japan",
        "url": "https://www.boj.or.jp/en/rss/whatsnew.xml",
        "currencies": ["JPY"],
        "color": 0xBC002D,
    },
    "boc": {
        "name": "Bank of Canada",
        "url": "https://www.bankofcanada.ca/content_type/press-releases/feed/",
        "currencies": ["CAD"],
        "color": 0xD52B1E,
    },
    "snb": {
        "name": "SNB",
        "url": "https://www.snb.ch/public/en/rss/pressrel",
        "currencies": ["CHF"],
        "color": 0xE30613,
    },
    "cpi": {
        "name": "BLS - inflation (CPI)",
        "url": "https://www.bls.gov/feed/cpi.rss",
        "currencies": ["USD"],
        "color": 0x2E7D32,
    },
    "nfp": {
        "name": "BLS - emploi (NFP)",
        "url": "https://www.bls.gov/feed/empsit.rss",
        "currencies": ["USD"],
        "color": 0x2E7D32,
    },
    "ppi": {
        "name": "BLS - prix producteurs (PPI)",
        "url": "https://www.bls.gov/feed/ppi.rss",
        "currencies": ["USD"],
        "color": 0x2E7D32,
    },
    "bea": {
        "name": "BEA (PIB, PCE)",
        "url": "https://apps.bea.gov/rss/rss.xml",
        "currencies": ["USD"],
        "color": 0x2E7D32,
    },
    "eia": {
        "name": "EIA (énergie)",
        "url": "https://www.eia.gov/rss/todayinenergy.xml",
        "currencies": ["OIL"],
        "color": 0x5D4037,
    },
}

# mots qui font passer une news en "impact élevé"
HIGH_IMPACT_WORDS = [
    "interest rate", "policy rate", "bank rate", "monetary policy", "fomc",
    "rate decision", "inflation", "consumer price", "cpi", "ppi", "producer price",
    "employment situation",
    "payroll", "unemployment", "gdp", "gross domestic product", "pce",
    "personal income", "minutes", "press conference", "statement",
]

# mots qui ajoutent l'or quand la news parle de taux / inflation
GOLD_WORDS = ["interest rate", "inflation", "monetary policy", "fomc", "gold"]


def fetch(key, limit=10):
    """Télécharge une source et renvoie ses dernières news (la plus récente en premier)."""
    source = SOURCES[key]
    feed = feedparser.parse(source["url"], agent=USER_AGENT)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"flux illisible ({source['name']}) : {feed.bozo_exception}")

    items = []
    for entry in feed.entries[:limit]:
        link = entry.get("link", "").strip()
        if not link:
            continue
        title = entry.get("title", "Sans titre").strip()
        items.append({
            "id": entry.get("id") or link,
            "source": key,
            "title": title[:250],
            "link": link,
            "summary": clean_summary(entry.get("summary", "")),
            "date": entry_date(entry),
            "currencies": currencies_for(source, title),
            "high_impact": is_high_impact(title),
        })
    return items


def is_high_impact(title):
    t = title.lower()
    return any(word in t for word in HIGH_IMPACT_WORDS)


def currencies_for(source, title):
    currencies = list(source["currencies"])
    t = title.lower()
    if "USD" in currencies and any(word in t for word in GOLD_WORDS):
        currencies.append("XAU")
    return currencies


def entry_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
    return None


def clean_summary(text, max_len=300):
    # feedparser laisse parfois du HTML dans le résumé, on enlève les balises
    out = ""
    inside_tag = False
    for c in text:
        if c == "<":
            inside_tag = True
        elif c == ">":
            inside_tag = False
        elif not inside_tag:
            out += c
    out = " ".join(out.split())
    if len(out) > max_len:
        out = out[:max_len].rsplit(" ", 1)[0] + "..."
    return out


if __name__ == "__main__":
    # test rapide sans Discord : python news.py
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # la console Windows plante sur certains accents
    for key in SOURCES:
        try:
            items = fetch(key, limit=3)
            print(f"[OK] {key}: {len(items)} news")
            for item in items:
                flag = "!" if item["high_impact"] else " "
                print(f"   {flag} {','.join(item['currencies']):8} {item['title'][:80]}")
        except Exception as e:
            print(f"[ERREUR] {key}: {e}")
