# Usage: python3 -I tools/validate.py data.json
# Checks the planner data before publishing. Exits non-zero and lists every problem it finds.
import json, re, sys

data = json.load(open(sys.argv[1]))
errors, warnings = [], []
err = errors.append
warn = warnings.append

trip = data.get("trip", {})
for k in ("title", "start", "end", "origin", "storagePrefix"):
    if k not in trip: err(f"trip.{k} is missing")
for k in ("start", "end"):
    if k in trip and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", trip[k]): err(f"trip.{k} must be YYYY-MM-DD")
o = trip.get("origin", {})
if "address" not in o: err("trip.origin.address is missing")
if "lat" not in o or "lon" not in o: warn("trip.origin has no lat/lon: run tools/geo.py (weather, map and real distances need it)")

types = {t["id"] for t in data.get("types", [])}
areas = {a["id"] for a in data.get("areas", [])}
photos = data.get("photos", {})
ids = set()
for i, p in enumerate(data.get("places", [])):
    where = f'place {p.get("id", i)}'
    for k in ("id", "a", "n", "t", "q", "note"):
        if not p.get(k): err(f"{where}: {k} is missing")
    if p.get("id") in ids: err(f"{where}: duplicate id")
    ids.add(p.get("id"))
    if p.get("id") and not re.fullmatch(r"[a-z0-9-]+", p["id"]): err(f"{where}: id should be lowercase letters, digits and dashes")
    if p.get("a") not in areas: err(f'{where}: area "{p.get("a")}" is not in areas')
    for t in p.get("t", []):
        if t not in types: err(f'{where}: type "{t}" is not in types')
    if not isinstance(p.get("mi"), (int, float)) or not isinstance(p.get("min"), (int, float)):
        err(f"{where}: mi and min must be numbers")
    if p.get("mode") not in (None, "driving", "walking"): err(f"{where}: mode must be driving or walking")
    if "lat" not in p: warn(f"{where}: no lat/lon, so it won't be on the map or in Near me")
    if p.get("web") and not p["web"].startswith("https://"): err(f"{where}: web must be an https URL")
    if p.get("photo") and p["photo"] not in photos: err(f'{where}: photo "{p["photo"]}" is not in photos')
    if p.get("phone") and not re.fullmatch(r"\+?[0-9 ]{9,16}", p["phone"]): err(f'{where}: phone "{p["phone"]}" looks wrong')
    if p.get("phone") and not p.get("phoneSource"): err(f"{where}: phone needs a phoneSource URL (where the number was found)")
    w = p.get("walk")
    if w is not None and "walk" not in p.get("t", []): warn(f"{where}: has walk details but isn't tagged walk")

DAYKEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DOG_WHERE = ("everywhere", "bar only", "separate dog area", "some areas", "outside only", "not allowed")
for p in data.get("places", []):
    where = f'place {p.get("id")}'
    h = p.get("hours")
    if h is not None:
        if set(h) - set(DAYKEYS): err(f"{where}: hours keys must be {', '.join(DAYKEYS)}")
        for k, v in h.items():
            if v != "closed" and not re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}(,\d{2}:\d{2}-\d{2}:\d{2})*", str(v)):
                err(f'{where}: hours.{k} "{v}" should be "HH:MM-HH:MM" (comma-separated) or "closed"')
        if not p.get("hoursSource"): err(f"{where}: hours need a hoursSource (a URL or \"OpenStreetMap\")")
    for dte in p.get("closedDates", []):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dte): err(f"{where}: closedDates must be YYYY-MM-DD")
    if p.get("dog"):
        if p["dog"].get("where") not in DOG_WHERE: err(f'{where}: dog.where must be one of {", ".join(DOG_WHERE)}')
    if p.get("baby") and not isinstance(p["baby"], dict): err(f"{where}: baby must be an object")
    if p.get("price") and p["price"] not in ("£", "££", "£££", "££££"): err(f'{where}: price must be £ to ££££')

for i, ev in enumerate(data.get("events", [])):
    where = f'event {ev.get("id", i)}'
    for k in ("id", "name", "date"):
        if not ev.get(k): err(f"{where}: {k} is missing")
    for k in ("date", "endDate"):
        if ev.get(k) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ev[k]): err(f"{where}: {k} must be YYYY-MM-DD")
    if ev.get("placeId") and ev["placeId"] not in ids: err(f'{where}: placeId "{ev["placeId"]}" is not a place')
    if not ev.get("url"): warn(f"{where}: no url (source)")

em = data.get("emergency", [])
for i, x in enumerate(em):
    if not x.get("name") or not (x.get("phone") or x.get("q")): err(f"emergency {i}: needs a name and a phone or q")
    if x.get("phone") and x["phone"] not in ("999", "111", "112") and not x.get("source"): err(f'emergency {x.get("name")}: phone needs a source')
if not em: warn("no emergency contacts (999, NHS 111, nearest A&E)")
if trip.get("dog") and not any(x.get("kind") == "vet-24h" for x in em):
    warn('a dog is coming but there is no out-of-hours vet in emergency (kind: "vet-24h")')

for title, ph in photos.items():
    for k in ("img", "page", "artist", "license"):
        if not ph.get(k): err(f'photo "{title}": {k} is missing (every photo needs a full credit)')
    lic = ph.get("license", "").lower()
    if lic and not any(s in lic for s in ("cc", "public domain", "pd")):
        err(f'photo "{title}": licence "{ph["license"]}" is not a free licence')

for a in areas:
    if not any(p.get("a") == a for p in data.get("places", [])): warn(f'area "{a}" has no places')

for w in warnings: print("warning:", w)
for e in errors: print("ERROR:", e)
print(f'{len(data.get("places", []))} places, {len(photos)} photos, {len(errors)} errors, {len(warnings)} warnings')
sys.exit(1 if errors else 0)
