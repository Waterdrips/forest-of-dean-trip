# Usage: python3 -I tools/check_links.py data.json
# Checks every website link and photo in the planner still loads. Prints a Markdown report and
# exits non-zero if any are broken (the weekly GitHub Action turns that into an issue).
import json, subprocess, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

data = json.load(open(sys.argv[1]))
UA = {"User-Agent": "Mozilla/5.0 (compatible; holiday-planner-linkcheck/1.0)"}

def check(item):
    label, url = item
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return label, url, r.status, None
        except urllib.error.HTTPError as e:
            # Wikimedia rate-limits scripts (429) but serves browsers fine: count it as working.
            if e.code == 429 and "wikimedia.org" in url: return label, url, 200, None
            # Some sites block bots with 401/403/429 even though the page is fine in a browser.
            if e.code in (401, 403, 429): return label, url, e.code, "blocked (probably fine in a browser)"
            err = f"HTTP {e.code}"
        except Exception as e:
            err = str(e)[:80]
            # Python's TLS can fail on sites a browser (and curl) open fine: double-check with curl.
            code = subprocess.run(["curl", "-s", "-L", "-o", "/dev/null", "-m", "25", "-A", UA["User-Agent"], "-w", "%{http_code}", url],
                                  capture_output=True, text=True).stdout.strip()
            if code.isdigit() and 200 <= int(code) < 400: return label, url, int(code), None
        time.sleep(2)
    return label, url, None, err

items = [(f'{p["n"]} (website)', p["web"]) for p in data["places"] if p.get("web")]
items += [(f"Photo: {t}", ph["img"]) for t, ph in data.get("photos", {}).items()]
items = list(dict((u, l) for l, u in items).items())
items = [(l, u) for u, l in items]

# Wikimedia rate-limits bursts, so photos are checked one at a time; websites in parallel.
def slow(item):
    time.sleep(1.5); return check(item)
sites = [i for i in items if "wikimedia.org" not in i[1]]
media = [i for i in items if "wikimedia.org" in i[1]]
with ThreadPoolExecutor(4) as ex:
    results = list(ex.map(check, sites))
results += [slow(i) for i in media]

broken = [r for r in results if r[2] is None]
blocked = [r for r in results if r[3] and r[2]]
print(f"Checked {len(results)} links: {len(broken)} broken, {len(blocked)} blocked.\n")
if broken:
    print("### Broken\n")
    for l, u, _, e in broken: print(f"- [ ] **{l}**: {u} ({e})")
if blocked:
    print("\n### Blocked by the site (check by hand if unsure)\n")
    for l, u, c, e in blocked: print(f"- {l}: {u} ({c})")
sys.exit(1 if broken else 0)
