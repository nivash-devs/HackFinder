#!/usr/bin/env python3
"""HackFinder scraper.

Reads public event listings from Hack Club, Devpost, MLH and itch.io,
turns them into one common format, removes duplicates, finds map
coordinates for each in-person event, and writes site/events.json.

Nobody has to submit anything. If an event is public on one of these
sites, it shows up here on the next run.
"""
import datetime as dt
import functools
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "events.json"
CACHE_FILE = ROOT / "data" / "geocache.json"

# Nominatim (the free OpenStreetMap geocoder) asks every app to identify itself.
# Put your GitHub repo link here once you have one.
USER_AGENT = "HackFinder/0.1 (student project; https://github.com/nivash-devs/HackFinder)"

print = functools.partial(print, flush=True)  # show progress live in the GitHub log
S = requests.Session()
S.headers["User-Agent"] = USER_AGENT

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ---------- helpers ----------

def load_cache():
    try:
        c = json.loads(CACHE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        c = {}
    c.setdefault("geo", {})
    c.setdefault("devpost_address", {})
    return c


def save_cache(c):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(c, indent=1, sort_keys=True, ensure_ascii=False))


def make_event(**kw):
    e = {
        "name": None, "url": None, "source": None,
        "start": None, "end": None,      # ISO date or datetime strings
        "mode": "in-person",             # in-person | online | hybrid
        "place": None,                   # human readable location
        "lat": None, "lng": None,
        "image": None, "tags": [], "extra": None,
    }
    e.update(kw)
    e["sources"] = [{"name": e["source"], "url": e["url"]}]
    return e


def get(url, **kw):
    r = S.get(url, timeout=30, **kw)
    r.raise_for_status()
    return r


def geocode(query, cache):
    """City/address text -> [lat, lng] using OpenStreetMap. Cached, max 1 request/second."""
    if not query:
        return None
    key = re.sub(r"\s+", " ", query.strip().lower())
    if key in cache["geo"]:
        return cache["geo"][key]
    time.sleep(1.1)  # Nominatim usage policy: at most 1 request per second
    try:
        res = get("https://nominatim.openstreetmap.org/search",
                  params={"q": query, "format": "json", "limit": 1}).json()
        val = [round(float(res[0]["lat"]), 5), round(float(res[0]["lon"]), 5)] if res else None
    except Exception as ex:  # network hiccup: don't cache, try again next run
        print(f"  geocode failed for {query!r}: {ex}", file=sys.stderr)
        return None
    cache["geo"][key] = val
    return val


def geocode_place(place, cache):
    """Full addresses like 'Student Union Bldg, 6138 Student Union Blvd #2201, Vancouver, BC V6T 1Z1, Canada'
    often fail. If one does, drop the first part (building name, then street) and retry,
    down to just 'city, region, country'. Close enough for a radius search."""
    parts = [p.strip() for p in place.split(",") if p.strip()]
    for i in range(len(parts)):
        rest = parts[i:]
        if i > 0 and len(rest) < 2:
            break
        q = ", ".join(rest)
        q = re.sub(r"\s*#[^,\s]+", "", q)  # suite numbers confuse the geocoder
        ll = geocode(q, cache)
        if ll:
            return ll
    return None


def parse_devpost_dates(text):
    """'Oct 30 - Dec 04, 2026' / 'Nov 14 - 15, 2026' / 'Nov 11, 2026 - Jan 11, 2027' / 'Nov 14, 2026'"""
    if not text:
        return None, None
    s = text.replace("–", "-").strip()
    m = re.match(r"([A-Za-z]+) (\d{1,2})(?:, (\d{4}))?\s*-\s*(?:([A-Za-z]+) )?(\d{1,2}), (\d{4})$", s)
    try:
        if m:
            m1, d1, y1, m2, d2, y2 = m.groups()
            m2 = m2 or m1
            start = dt.date(int(y1 or y2), MONTHS[m1[:3].lower()], int(d1))
            end = dt.date(int(y2), MONTHS[m2[:3].lower()], int(d2))
            if start > end and not y1:  # e.g. "Dec 28 - Jan 03, 2027"
                start = start.replace(year=start.year - 1)
            return start.isoformat(), end.isoformat()
        m = re.match(r"([A-Za-z]+) (\d{1,2}), (\d{4})$", s)
        if m:
            d = dt.date(int(m[3]), MONTHS[m[1][:3].lower()], int(m[2])).isoformat()
            return d, d
    except (KeyError, ValueError):
        pass
    return None, None


def parse_duration(text):
    """itch.io durations like '4 days', '2 weeks', '1 month', '48 hours' -> timedelta"""
    m = re.match(r"(\d+)\s*(hour|day|week|month|year)", (text or "").lower())
    if not m:
        return None
    n, unit = int(m[1]), m[2]
    return dt.timedelta(hours=n) if unit == "hour" else dt.timedelta(
        days=n * {"day": 1, "week": 7, "month": 30, "year": 365}[unit])


# ---------- sources ----------

def from_hackclub(cache):
    """hackathons.hackclub.com: high-school hackathons, already has coordinates."""
    for e in get("https://hackathons.hackclub.com/api/events/upcoming").json():
        mode = "hybrid" if e.get("hybrid") else ("online" if e.get("virtual") else "in-person")
        place = ", ".join(x for x in [e.get("city"), e.get("state"), e.get("country")] if x) or None
        yield make_event(
            name=e.get("name"), url=e.get("website"), source="Hack Club",
            start=e.get("start"), end=e.get("end"), mode=mode, place=place,
            lat=e.get("latitude"), lng=e.get("longitude"), image=e.get("logo"),
            tags=["High school"] + (["MLH"] if e.get("mlhAssociated") else []),
        )


def devpost_address(page_url, cache):
    """Devpost's list only says the venue ('Morgridge Hall'). The event page links to
    Google Maps with the full street address, so read it from there. Cached by URL."""
    if page_url in cache["devpost_address"]:
        return cache["devpost_address"][page_url]
    addr = None
    try:
        time.sleep(0.5)
        soup = BeautifulSoup(get(page_url).text, "html.parser")
        a = soup.select_one('.info-with-icon a[href*="maps.google"]')
        if a:
            q = parse_qs(urlparse(a["href"]).query).get("q")
            addr = q[0] if q else None
    except Exception as ex:
        print(f"  devpost page failed {page_url}: {ex}", file=sys.stderr)
        return None
    cache["devpost_address"][page_url] = addr
    return addr


def from_devpost(cache, max_pages=40):
    """devpost.com public hackathon list (upcoming + open)."""
    for page in range(1, max_pages + 1):
        data = get("https://devpost.com/api/hackathons",
                   params=[("status[]", "upcoming"), ("status[]", "open"), ("page", page)]).json()
        items = data.get("hackathons") or []
        if not items:
            break
        for h in items:
            loc = (h.get("displayed_location") or {})
            online = loc.get("icon") == "globe" or (loc.get("location") or "").lower() == "online"
            start, end = parse_devpost_dates(h.get("submission_period_dates"))
            url = h.get("url")
            place = None if online else (devpost_address(url, cache) or loc.get("location"))
            thumb = h.get("thumbnail_url")
            yield make_event(
                name=h.get("title"), url=url, source="Devpost", start=start, end=end,
                mode="online" if online else "in-person", place=place,
                image=("https:" + thumb) if thumb and thumb.startswith("//") else thumb,
                tags=[t["name"] for t in h.get("themes", [])][:3],
                extra=f'{h.get("registrations_count", 0):,} registered' if h.get("registrations_count") else None,
            )
        time.sleep(0.5)


def mlh_season(today):
    # MLH seasons run roughly August to July and are named after the year they end in.
    return today.year + 1 if today.month >= 7 else today.year


def from_mlh(cache, today=None):
    """mlh.com season schedule. Each card is tagged with schema.org Event data."""
    season = mlh_season(today or dt.date.today())
    soup = BeautifulSoup(get(f"https://www.mlh.com/seasons/{season}/events").text, "html.parser")
    for card in soup.select('[itemtype*="schema.org/Event"]'):
        def meta(p):
            t = card.select_one(f'meta[itemprop="{p}"]')
            return t.get("content") if t else None
        title = card.select_one("h4, h3")
        mode_raw = meta("eventAttendanceMode") or ""
        mode = "online" if "Online" in mode_raw else "hybrid" if "Mixed" in mode_raw else "in-person"
        place = ", ".join(x for x in [meta("addressLocality"), meta("addressRegion"), meta("addressCountry")] if x)
        yield make_event(
            name=title.get_text(strip=True) if title else None, url=meta("url"), source="MLH",
            start=meta("startDate"), end=meta("endDate"), mode=mode, place=place or None,
            image=meta("image"), tags=["MLH"],
        )


def from_itch(cache, today=None):
    """itch.io game jams. Almost all are online."""
    now = dt.datetime.combine(today or dt.date.today(), dt.time())
    for path in ("upcoming", "in-progress"):
        soup = BeautifulSoup(get(f"https://itch.io/jams/{path}").text, "html.parser")
        for j in soup.select("div.jam"):
            a = j.select_one("h3 a")
            if not a:
                continue
            row = j.select_one(".timestmap, .timestamp")  # itch.io's class really is spelled 'timestmap'
            cd = j.select_one(".date_countdown[title]")
            dur = parse_duration((j.select_one(".date_duration") or {}).get_text() if j.select_one(".date_duration") else "")
            start = end = None
            if cd:
                when = dt.datetime.strptime(cd["title"], "%Y-%m-%d %H:%M:%S")
                label = row.get_text(" ", strip=True).lower() if row else ""
                if "start" in label:
                    start = when
                    end = when + dur if dur else None
                else:  # in-progress jams show when they end
                    end = when
            if end and end < now:
                continue
            joined = j.select_one(".jam_stats .number")
            host = j.select_one(".hosted_by a")
            yield make_event(
                name=a.get_text(strip=True), url=urljoin("https://itch.io", a["href"]), source="itch.io",
                start=start.isoformat() + "Z" if start else None, end=end.isoformat() + "Z" if end else None,
                mode="online", tags=["Game jam"],
                extra=" · ".join(x for x in [
                    f"{joined.get_text(strip=True)} joined" if joined else None,
                    f"by {host.get_text(strip=True)}" if host else None] if x) or None,
            )


SOURCES = [("Hack Club", from_hackclub), ("Devpost", from_devpost), ("MLH", from_mlh), ("itch.io", from_itch)]


# ---------- clean-up ----------

def norm_name(name):
    n = (name or "").lower()
    n = re.sub(r"\b(19|20)\d{2}\b|'\d{2}\b|\b[ivx]+\b|\bfall\b|\bspring\b|\bv\d+\b", " ", n)
    return re.sub(r"[^a-z0-9]", "", n)


def day(s):
    try:
        return dt.date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def dedupe(events):
    """The same hackathon is often on MLH and Devpost. Merge those into one card."""
    out = []
    for e in events:
        k, d = norm_name(e["name"]), day(e["start"])
        twin = None
        for o in out:
            ok, od = norm_name(o["name"]), day(o["start"])
            if k and ok and (k in ok or ok in k) and d and od and abs((d - od).days) <= 2:
                twin = o
                break
        if not twin:
            out.append(e)
            continue
        twin["sources"] += [s for s in e["sources"] if s["name"] not in {x["name"] for x in twin["sources"]}]
        for f in ("lat", "lng", "place", "image", "end", "extra"):
            if twin.get(f) is None and e.get(f) is not None:
                twin[f] = e[f]
        twin["tags"] = list(dict.fromkeys(twin["tags"] + e["tags"]))
    return out


def main():
    cache = load_cache()
    today = dt.date.today()
    events, status = [], {}
    for name, fn in SOURCES:
        try:
            got = list(fn(cache))
            status[name] = {"ok": True, "count": len(got)}
            events += got
            print(f"{name}: {len(got)} events")
        except Exception as ex:  # one broken site shouldn't take the others down
            status[name] = {"ok": False, "error": str(ex)[:200]}
            print(f"{name}: FAILED {ex}", file=sys.stderr)

    # drop anything already over, and anything with no name or link
    events = [e for e in events if e["name"] and e["url"] and not (day(e["end"]) and day(e["end"]) < today)]
    events = dedupe(events)

    for e in events:
        if e["mode"] != "online" and e["lat"] is None and e["place"]:
            ll = geocode_place(e["place"], cache)
            if ll:
                e["lat"], e["lng"] = ll
        e.pop("source", None)

    events.sort(key=lambda e: e["start"] or e["end"] or "9999")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sources": status,
        "events": events,
    }, ensure_ascii=False, indent=1))
    save_cache(cache)
    print(f"Wrote {len(events)} events to {OUT}")
    return 0 if any(s["ok"] for s in status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
