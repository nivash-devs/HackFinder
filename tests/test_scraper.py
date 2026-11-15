"""Offline tests. The fake pages below copy the real structure of each site
(checked Nov 2026), so if a site changes its layout these tell you which parser broke."""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scraper"))
import fetch_events as fe  # noqa: E402

HACKCLUB = [
    {"id": "a", "name": "Earth Hacks 2027", "website": "https://earthhacks.dev", "start": "2027-01-23T17:00:00.000Z",
     "end": "2027-01-24T05:30:00.000Z", "logo": "https://x/logo.png", "city": "San Francisco", "state": "California",
     "country": "United States", "latitude": 37.78, "longitude": -122.42, "virtual": False, "hybrid": False,
     "mlhAssociated": False},
    {"id": "b", "name": "Cosmo Hacks", "website": "https://cosmo.dev", "start": "2027-02-01T00:00:00Z",
     "end": "2027-02-02T00:00:00Z", "city": None, "state": None, "country": None, "latitude": None,
     "longitude": None, "virtual": True, "hybrid": False},
]
DEVPOST_P1 = {"hackathons": [
    {"title": "MadHacks 2026", "displayed_location": {"icon": "map-marker-alt", "location": "Morgridge Hall"},
     "url": "https://madhacks-fall-2026.devpost.com/", "submission_period_dates": "Nov 14 - 15, 2026",
     "thumbnail_url": "//cdn/x.png", "themes": [{"id": 1, "name": "Open Ended"}], "registrations_count": 146},
    {"title": "Kiroween 2026", "displayed_location": {"icon": "globe", "location": "Online"},
     "url": "https://kiroween.devpost.com/", "submission_period_dates": "Oct 30 - Dec 04, 2026", "themes": []},
    {"title": "HackUTA '26", "displayed_location": {"icon": "map-marker-alt", "location": "University of Texas at Arlington"},
     "url": "https://hackuta.devpost.com/", "submission_period_dates": "Nov 14 - 15, 2026", "themes": []},
], "meta": {}}
DEVPOST_PAGE = '''<div class="info-with-icon"><i class="fas fa-map-marker-alt"></i><div class="info">
<a target="_blank" href="https://maps.google.com/?q=1205%20University%20Ave%2C%20Madison%2C%20WI%2053706%2C%20USA">Morgridge Hall</a></div></div>'''
MLH_PAGE = '''<div class="grid"><a href="https://hackuta.com" itemscope itemtype="http://schema.org/Event">
<meta itemprop="url" content="https://hackuta.com/"><meta itemprop="eventAttendanceMode" content="https://schema.org/OfflineEventAttendanceMode">
<meta itemprop="image" content="https://mlh/x.png"><meta itemprop="startDate" content="2026-11-14T15:00:00Z"><meta itemprop="endDate" content="2026-11-15T22:00:00Z">
<div itemprop="location" itemscope itemtype="http://schema.org/Place"><span itemprop="name">Arlington, Texas</span>
<div itemprop="address" itemscope itemtype="http://schema.org/PostalAddress"><meta itemprop="addressLocality" content="Arlington">
<meta itemprop="addressRegion" content="Texas"><meta itemprop="addressCountry" content="US"></div></div>
<div><h4 class="font-bold">HackUTA</h4><span>NOV 14 - 15</span></div></a></div>'''
ITCH_UPCOMING = '''<div class="jam"><div class="padded_content"><div class="jam_top_row"><div class="primary_info">
<h3 dir="auto"><a href="/jam/gmtk-2027">GMTK Game Jam 2027</a></h3></div></div>
<div class="hosted_by meta_row">Hosted by <a href="https://gmtk.itch.io">Game Maker's Toolkit</a></div>
<div class="timestmap meta_row"><strong>Starts in <span title="2027-08-11 17:00:00" class="date_countdown">8 months</span></strong> · Lasts <span class="date_duration">4 days</span></div>
<div class="jam_stats"><div class="stat"><span class="number">2,042</span> joined</div></div></div></div>'''
ITCH_RUNNING = '''<div class="jam"><div class="padded_content"><h3><a href="/jam/old">Old Jam</a></h3>
<div class="timestmap meta_row"><strong>Ends in <span title="2020-01-01 00:00:00" class="date_countdown">x</span></strong></div></div></div>
<div class="jam"><div class="padded_content"><h3><a href="/jam/live">Live Jam</a></h3>
<div class="timestmap meta_row"><strong>Submission due in <span title="2099-01-01 00:00:00" class="date_countdown">x</span></strong></div></div></div>'''


class Resp:
    def __init__(self, body):
        self.body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        return self.body if not isinstance(self.body, str) else json.loads(self.body)


def fake_get(url, **kw):
    params = dict(kw.get("params") or [])
    if "hackclub" in url:
        return Resp(HACKCLUB)
    if url == "https://devpost.com/api/hackathons":
        return Resp(DEVPOST_P1 if params.get("page") == 1 else {"hackathons": []})
    if "madhacks" in url:
        return Resp(DEVPOST_PAGE)
    if "devpost.com" in url:
        return Resp("<html></html>")
    if "mlh.com" in url:
        return Resp(MLH_PAGE)
    if url.endswith("/jams/upcoming"):
        return Resp(ITCH_UPCOMING)
    if url.endswith("/jams/in-progress"):
        return Resp(ITCH_RUNNING)
    raise AssertionError("unexpected url " + url)


def setup():
    fe.get = fake_get
    fe.time.sleep = lambda s: None
    return {"geo": {}, "devpost_address": {}}


def test_dates():
    assert fe.parse_devpost_dates("Oct 30 - Dec 04, 2026") == ("2026-10-30", "2026-12-04")
    assert fe.parse_devpost_dates("Nov 14 - 15, 2026") == ("2026-11-14", "2026-11-15")
    assert fe.parse_devpost_dates("Nov 11, 2026 - Jan 11, 2027") == ("2026-11-11", "2027-01-11")
    assert fe.parse_devpost_dates("Dec 28 - Jan 03, 2027") == ("2026-12-28", "2027-01-03")
    assert fe.parse_devpost_dates("Nov 14, 2026") == ("2026-11-14", "2026-11-14")
    assert fe.parse_devpost_dates("garbage") == (None, None)


def test_sources():
    c = setup()
    hc = list(fe.from_hackclub(c))
    assert hc[0]["lat"] == 37.78 and hc[0]["mode"] == "in-person" and hc[1]["mode"] == "online"
    dp = list(fe.from_devpost(c))
    assert len(dp) == 3
    assert dp[0]["place"] == "1205 University Ave, Madison, WI 53706, USA"
    assert dp[1]["mode"] == "online" and dp[1]["place"] is None
    assert dp[2]["place"] == "University of Texas at Arlington"  # fallback when page has no map link
    ml = list(fe.from_mlh(c, today=dt.date(2026, 11, 15)))
    assert ml[0]["name"] == "HackUTA" and ml[0]["place"] == "Arlington, Texas, US"
    it = list(fe.from_itch(c, today=dt.date(2026, 11, 15)))
    names = [e["name"] for e in it]
    assert names == ["GMTK Game Jam 2027", "Live Jam"], names
    assert it[0]["start"] == "2027-08-11T17:00:00Z" and it[0]["end"] == "2027-08-15T17:00:00Z"
    assert "2,042 joined" in it[0]["extra"]


def test_dedupe_merges_mlh_and_devpost():
    c = setup()
    evs = list(fe.from_devpost(c)) + list(fe.from_mlh(c, today=dt.date(2026, 11, 15)))
    out = fe.dedupe(evs)
    uta = [e for e in out if "HackUTA" in e["name"]]
    assert len(uta) == 1
    assert {s["name"] for s in uta[0]["sources"]} == {"Devpost", "MLH"}


def test_season():
    assert fe.mlh_season(dt.date(2026, 11, 15)) == 2027
    assert fe.mlh_season(dt.date(2027, 3, 1)) == 2027


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("pass", name)
