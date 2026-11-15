"""Builds tests/sample-events.json from the offline fixtures, for previewing the page."""
import datetime as dt, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import test_scraper as t
fe = t.fe
c = t.setup()
evs = list(fe.from_hackclub(c)) + list(fe.from_devpost(c)) + list(fe.from_mlh(c, today=dt.date(2026,11,15))) + list(fe.from_itch(c, today=dt.date(2026,11,15)))
evs = fe.dedupe(evs)
coords = {"1205 University Ave, Madison, WI 53706, USA": (43.0727, -89.4075), "University of Texas at Arlington": (32.7299, -97.1153)}
for e in evs:
    if e["place"] in coords: e["lat"], e["lng"] = coords[e["place"]]
    e.pop("source", None)
evs.append({"name":"Hack Peel","url":"https://example.org","sources":[{"name":"Hack Club","url":"https://example.org"}],"start":"2027-02-20","end":"2027-02-21","mode":"in-person","place":"Mississauga, Ontario, Canada","lat":43.59,"lng":-79.64,"image":None,"tags":["High school"],"extra":None})
json.dump({"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "sources":{"Hack Club":{"ok":True,"count":3},"Devpost":{"ok":True,"count":3},"MLH":{"ok":True,"count":1},"itch.io":{"ok":True,"count":2}}, "events": evs}, open(Path(__file__).parent/"sample-events.json","w"), indent=1)
print(len(evs))
