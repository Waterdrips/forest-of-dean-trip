# Usage: python3 -I tools/hours.py data.json [--force]
# Looks up opening hours on OpenStreetMap for every place that has coordinates (run tools/geo.py first).
# It matches each place to a nearby OpenStreetMap feature with a similar name and an opening_hours tag, then
# stores "hoursRaw" (the OSM text), "hours" ({"mon": "12:00-21:00" | "closed", ...}) and "hoursSource".
# OpenStreetMap hours can be out of date, so the page labels them as such. Hours you set by hand
# (hoursSource that isn't OpenStreetMap) are kept unless --force.
import json, math, re, subprocess, sys, time, urllib.parse

path = sys.argv[1]; force = "--force" in sys.argv
data = json.load(open(path))
DAYS = ["mo", "tu", "we", "th", "fr", "sa", "su"]
KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def overpass(query):
    for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        out = subprocess.run(["curl", "-sf", "-m", "180", "-A", "holiday-planner/1.0", "--data-urlencode", "data=" + query, url],
                             capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip().startswith("{"): return json.loads(out.stdout)
        time.sleep(5)
    sys.exit("Overpass (OpenStreetMap) didn't answer; try again later")

MONTHS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]

def closed_dates(oh):
    """Dated closures such as "2026 Oct 10-14 off" -> ["2026-10-10", ...]."""
    out = []
    for y, mon, a, b in re.findall(r"\b(\d{4}) ([A-Z][a-z]{2}) (\d{1,2})(?:-(\d{1,2}))? off\b", oh):
        if mon.lower() not in MONTHS: continue
        for d in range(int(a), int(b or a) + 1): out.append(f"{y}-{MONTHS.index(mon.lower())+1:02d}-{d:02d}")
    return out

def parse(oh):
    try: return _parse(oh)
    except (ValueError, IndexError): return None

def _parse(oh):
    """Parse the common forms of OSM opening_hours into per-day ranges. Returns None if it's too complex."""
    oh = ";".join(r for r in oh.split(";") if not re.match(r"\s*\d{4} [A-Z][a-z]{2} \d", r)).strip()  # dated closures handled separately
    if oh == "24/7": return {k: "00:00-24:00" for k in KEYS}
    if re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|week|sunrise|sunset|easter)\b", oh, re.I): return None
    res = {}
    for rule in [r.strip() for r in oh.split(";") if r.strip()]:
        rule = re.sub(r"\bPH\b[^,; ]*,?\s*", "", rule).strip().rstrip(",")
        m = re.match(r"^((?:[A-Z][a-z](?:-[A-Z][a-z])?(?:\[[^\]]*\])?,?\s*)+)\s*(.*)$", rule)
        if not m:
            if re.fullmatch(r"[\d:,\- ]+", rule): days, times = list(range(7)), rule   # times with no days = every day
            else: return None
        else:
            days = []
            for part in re.split(r",\s*", m.group(1).strip().rstrip(",")):
                if "[" in part: return None
                if "-" in part:
                    a, b = [DAYS.index(x.lower()) for x in part.split("-")]
                    days += list(range(a, b + 1)) if a <= b else list(range(a, 7)) + list(range(0, b + 1))
                elif part: days.append(DAYS.index(part.lower()))
            times = m.group(2).strip()
        if times.lower() in ("off", "closed"): val = "closed"
        elif re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}\+?(,\s*\d{2}:\d{2}-\d{2}:\d{2}\+?)*", times): val = re.sub(r"\s", "", times).replace("+", "")
        elif not times: continue
        else: return None
        for d in days: res[KEYS[d]] = val
    for k in KEYS: res.setdefault(k, "closed")  # OSM: days not mentioned are closed
    return res

GENERIC = {"lounge", "bakery", "bar", "kitchen", "deli", "delicatessen", "tea", "room", "rooms", "shop", "bistro", "grill",
           "arms", "tavern", "castle", "abbey", "farm", "centre", "lake", "railway", "caves", "garden", "gardens", "village", "park"}

def norm(s):
    s = re.sub(r"\(.*?\)", "", s.lower().split(",")[0])
    s = re.sub(r"\b(the|inn|cafe|café|pub|hotel|restaurant|coffee|house|tea ?rooms?|&|and)\b", " ", s)
    return set(re.findall(r"[a-z0-9']{3,}", s))

# Only venues have opening hours; towns, walks and essentials searches would match unrelated shops.
VENUE = {"breakfast", "lunch", "dinner", "food", "todo", "rainy"}
places = [p for p in data["places"] if "lat" in p and VENUE & set(p["t"]) and not p.get("web", "").startswith("https://www.google")
          and (force or not p.get("hoursSource") or p["hoursSource"] == "OpenStreetMap")]
if not places: sys.exit("No places with coordinates; run tools/geo.py first")
pad = 0.01
s, w = min(p["lat"] for p in places) - pad, min(p["lon"] for p in places) - pad
n, e = max(p["lat"] for p in places) + pad, max(p["lon"] for p in places) + pad
q = f'[out:json][timeout:170];nwr["opening_hours"]["name"]({s},{w},{n},{e});out center tags;'
# Cache the area query for a day (Overpass rate-limits repeat queries).
import os
cache = os.path.join(os.path.dirname(os.path.abspath(path)), ".hours-cache.json")
c = json.load(open(cache)) if os.path.exists(cache) else {}
if c.get("q") == q and time.time() - c.get("at", 0) < 86400: els = c["els"]
else:
    els = overpass(q)["elements"]
    json.dump({"q": q, "at": time.time(), "els": els}, open(cache, "w"))
print(f"{len(els)} OpenStreetMap features with opening hours in the area", file=sys.stderr)

def dist_m(a_lat, a_lon, b_lat, b_lon):
    return 6371000 * math.hypot(math.radians(b_lat - a_lat), math.radians(b_lon - a_lon) * math.cos(math.radians(a_lat)))

found = 0
for p in places:
    want = norm(p["n"]) - norm(p.get("town", ""))  # match on the venue's own name, not its town
    specific = want - GENERIC  # "Wigmores Bakery" must match on "wigmores", not "bakery"
    if specific: want = specific
    best = None
    for el in els:
        lat = el.get("lat", el.get("center", {}).get("lat")); lon = el.get("lon", el.get("center", {}).get("lon"))
        if lat is None: continue
        d = dist_m(p["lat"], p["lon"], lat, lon)
        if d > 400: continue
        names = norm(el["tags"]["name"])
        overlap = len(want & names)
        if overlap and (best is None or (overlap, -d) > best[0]): best = ((overlap, -d), el)
    if not best: continue
    raw = best[1]["tags"]["opening_hours"]
    p["hoursRaw"], p["hours"], p["hoursSource"] = raw, parse(raw), "OpenStreetMap"
    p["hoursName"] = best[1]["tags"]["name"]
    if p["hours"] is None: p.pop("hours")
    cd = closed_dates(raw)
    if cd: p["closedDates"] = cd
    else: p.pop("closedDates", None)
    found += 1
    print(f'ok {p["id"]:12} {best[1]["tags"]["name"][:30]:30} {raw}', file=sys.stderr)

json.dump(data, open(path, "w"), indent=1, ensure_ascii=False)
print(f"hours found for {found} of {len(places)} places", file=sys.stderr)
