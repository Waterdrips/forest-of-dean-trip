# Usage: python3 -I tools/geo.py data.json [--force]
# Fills in lat/lon for the base and every place (OpenStreetMap Nominatim, 1 request/second),
# then real road distance and time from the base (OSRM: car for driving, foot for mode "walking").
# A place can set "geo": "better search text" or "lat"/"lon" by hand; those are kept unless --force.
# Set "fixedDistance": true to keep hand-set mi/min when routing gets one wrong.
# Places found only by their town get "geoApprox": true, and their distance is marked approximate on the page.
import json, re, subprocess, sys, time, urllib.request, urllib.parse
UA = {"User-Agent": "holiday-planner/1.0 (personal trip page)"}
path = sys.argv[1]; force = "--force" in sys.argv
data = json.load(open(path))

def get(url):
    try:  # curl copes with TLS setups that some older Python builds can't negotiate
        out = subprocess.run(["curl", "-sf", "-m", "40", "-A", UA["User-Agent"], url], capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip(): return json.loads(out.stdout)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
        except Exception as e:
            print("  retry", e, file=sys.stderr); time.sleep(3 * (i + 1))
    return None

def geocode(q):
    time.sleep(1.1)
    o = data["trip"]["origin"]
    params = {"q": q, "format": "jsonv2", "limit": 1, "countrycodes": data["trip"].get("countryCodes", "")}
    if "lat" in o:  # bias results towards the base
        d = 0.6
        params["viewbox"] = f'{o["lon"]-d},{o["lat"]+d},{o["lon"]+d},{o["lat"]-d}'
    r = get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params))
    return (float(r[0]["lat"]), float(r[0]["lon"])) if r else None

o = data["trip"]["origin"]
if force or "lat" not in o:
    ll = geocode(o.get("geo") or o["address"])
    pc = re.search(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b", o["address"].upper())
    if not ll and pc:  # UK postcode fallback
        r = get("https://api.postcodes.io/postcodes/" + urllib.parse.quote(pc.group(0)))
        if r and r.get("result"): ll = (r["result"]["latitude"], r["result"]["longitude"])
    if not ll: sys.exit("Could not find the base address; set trip.origin.lat/lon by hand")
    o["lat"], o["lon"] = ll
print("base", o["lat"], o["lon"], file=sys.stderr)

for p in data["places"]:
    if not force and "lat" in p: continue
    tries = [p.get("geo"), p["q"], p["n"].split(",")[0] + ", " + (p["n"].split(",")[1] if "," in p["n"] else "")]
    ll = None
    for q in [t for t in tries if t and t.strip(", ")]:
        ll = geocode(q)
        if ll: break
    approx = False
    if not ll and p.get("town"):
        ll = geocode(p["town"]); approx = True
    if not ll:
        print("NOT FOUND", p["id"], p["q"], file=sys.stderr); continue
    p["lat"], p["lon"] = round(ll[0], 5), round(ll[1], 5)
    if approx: p["geoApprox"] = True
    else: p.pop("geoApprox", None)
    print("ok", p["id"], ll, "(approx)" if approx else "", file=sys.stderr)

def route(profile_url, places):
    if not places: return
    coords = ";".join([f'{o["lon"]},{o["lat"]}'] + [f'{p["lon"]},{p["lat"]}' for p in places])
    r = get(f"{profile_url}/{coords}?sources=0&annotations=duration,distance")
    if not r or r.get("code") != "Ok": print("routing failed", r and r.get("code"), file=sys.stderr); return
    for p, sec, m in zip(places, r["durations"][0][1:], r["distances"][0][1:]):
        if sec is None: continue
        p["mi"] = round(m / 1609.34, 1)
        p["min"] = max(1, round(sec / 60))
        p["routed"] = True

located = [p for p in data["places"] if "lat" in p and not p.get("fixedDistance")]  # fixedDistance: keep hand-set mi/min
route("https://router.project-osrm.org/table/v1/driving", [p for p in located if p.get("mode") != "walking"])
time.sleep(1)
route("https://routing.openstreetmap.de/routed-foot/table/v1/foot", [p for p in located if p.get("mode") == "walking"])

json.dump(data, open(path, "w"), indent=1, ensure_ascii=False)
print("done", sum(1 for p in data["places"] if p.get("routed")), "routed of", len(data["places"]), file=sys.stderr)
