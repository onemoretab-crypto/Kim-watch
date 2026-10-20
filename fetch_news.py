#!/usr/bin/env python3
"""Collects headlines about Kim Jong Un (health, his daughter Kim Ju Ae, and changes
in his role or public appearances) and his sister Kim Yo Jong into data/news.json.
Stores only headline, link, source name and date (no article text)."""
import json, os, re, sys, urllib.request
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

def gn(query, lang="en", days=7):
    params = "hl=ko&gl=KR&ceid=KR:ko" if lang == "ko" else "hl=en-US&gl=US&ceid=US:en"
    return "https://news.google.com/rss/search?q=" + quote_plus(query) + "+when:%dd&" % days + params

# Add or remove feeds here. Any RSS feed works; stories are filtered below.
FEEDS = [
    {"name": "Google News", "lang": "en", "url": gn('"Kim Jong Un" health')},
    {"name": "Google News", "lang": "en", "url": gn('"Kim Ju Ae"')},
    {"name": "Google News", "lang": "en", "url": gn('"Kim Jong Un" daughter successor')},
    {"name": "Google News", "lang": "en", "url": gn('"Kim Jong Un" public appearance')},
    {"name": "Google News", "lang": "ko", "url": gn("김정은 건강", "ko")},
    {"name": "Google News", "lang": "ko", "url": gn("김주애", "ko")},
    {"name": "Google News", "lang": "ko", "url": gn("김정은 딸 후계", "ko")},
    {"name": "Google News", "lang": "en", "url": gn('"Kim Yo Jong"')},
    {"name": "Google News", "lang": "ko", "url": gn("김여정", "ko")},
    {"name": "SCMP", "lang": "en", "url": "https://www.scmp.com/rss/325001/feed"},
    {"name": "SCMP (KCNA)", "lang": "en", "url": "https://www.scmp.com/rss/522247/feed"},
    {"name": "NBC Bay Area", "lang": "en", "url": "https://www.nbcbayarea.com/tag/north-korea/feed/"},
    {"name": "NK News", "lang": "en", "url": "https://www.nknews.org/feed/"},
    {"name": "38 North", "lang": "en", "url": "https://www.38north.org/feed/"},
]
MAX_AGE_DAYS = 30
MAX_ITEMS = 120

# A headline must be about Kim Jong Un or his daughter...
ABOUT_KIM = re.compile(r"kim jong[- ]?un|kim ju[- ]?ae|north korean leader|north korea'?s leader|kim'?s daughter|김정은|김주애", re.I)
# Any headline about his sister is kept, whatever the topic.
SISTER = re.compile(r"kim yo[- ]?jong|kim jong[- ]?un'?s sister|김여정", re.I)
# Other headlines must also be about one of these topics.
HEALTH = re.compile(r"health|\bill\b|illness|\bsick|coma|hemorrhage|stroke|surgery|hospital|medical|weight|obes|cardio|heart|\blimp|\bcane\b|\bdeath\b|\bdies\b|\bdied\b|\bdead\b|건강|투병|혼수|사망|수술|병원|체중", re.I)
DAUGHTER = re.compile(r"ju[- ]?ae|daughter|successor|succession|heir|딸|주애|후계", re.I)
CHANGE = re.compile(r"appoint|promot|\btitle\b|new role|reshuffle|purge|handover|hand over|transfer|reappear|appearance|no-show|absen|disappear|missing|constitution|leadership|지위|직함|승계|공개활동|불참|등장|잠적", re.I)
# Words suggesting a health claim is a rumor rather than a confirmed fact.
HEDGE = re.compile(r"reportedly|rumou?r|speculat|alleg|unconfirmed|unverified|sources|claims?|may have|said to|coma|hemorrhage|이상설|건강설|사망설|루머|추정|혼수", re.I)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kim-watch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def classify(title):
    """Returns (category, unconfirmed) or None if the headline is off-topic."""
    kim = ABOUT_KIM.search(title)
    sister = SISTER.search(title)
    if not (kim or sister):
        return None
    if kim and HEALTH.search(title):
        return "health", bool(HEDGE.search(title))
    if sister:
        return "sister", False
    if DAUGHTER.search(title):
        return "daughter", False
    if CHANGE.search(title):
        return "changes", False
    return None

def parse(xml_bytes, feed):
    out = []
    for item in ET.fromstring(xml_bytes).iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = item.findtext("pubDate")
        if not (title and link and date):
            continue
        source = feed["name"]
        src = item.find("source")
        if src is not None and (src.text or "").strip():
            source = src.text.strip()
            suffix = " - " + source
            if title.endswith(suffix):
                title = title[: -len(suffix)].strip()
        result = classify(title)
        if not result:
            continue
        try:
            published = parsedate_to_datetime(date).astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        out.append({"title": title, "link": link, "source": source, "lang": feed["lang"],
                    "published": published.isoformat(), "category": result[0],
                    "unconfirmed": result[1]})
    return out

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    items, seen, ok = [], set(), 0
    for feed in FEEDS:
        try:
            found = parse(fetch(feed["url"]), feed)
            ok += 1
        except Exception as e:
            print("Feed failed:", feed["url"], e, file=sys.stderr)
            continue
        for it in found:
            key = re.sub(r"\W+", " ", it["title"].lower()).strip()
            if key in seen or datetime.fromisoformat(it["published"]) < cutoff:
                continue
            seen.add(key)
            items.append(it)
    if not ok:
        print("No feeds responded; keeping the previous file.", file=sys.stderr)
        sys.exit(1)
    items.sort(key=lambda i: i["published"], reverse=True)
    data = {"generated_at": datetime.now(timezone.utc).isoformat(), "items": items[:MAX_ITEMS]}
    os.makedirs("data", exist_ok=True)
    with open("data/news.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Wrote", len(data["items"]), "items from", ok, "feeds")

if __name__ == "__main__":
    main()
