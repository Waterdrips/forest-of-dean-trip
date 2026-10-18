# Usage: python3 -I tools/phones.py data.json [--force]
# For each place with a "web" link on the venue's or operator's own site, fetches the page and takes the
# phone number from its tel: link. Sets "phone" and "phoneSource" (the page it came from).
# Aggregator and tourism sites are skipped: their numbers might belong to a different venue.
import json, re, sys, time, urllib.request
from urllib.parse import urlparse

SKIP = ("visitdeanwye", "visitmonmouthshire", "visitrossonwye", "colefordtown", "google.", "tripadvisor", "wanderlog")
UA = {"User-Agent": "Mozilla/5.0 (holiday-planner phone lookup)"}
path = sys.argv[1]; force = "--force" in sys.argv
data = json.load(open(path))
pages = {}

def fetch(url):
    if url not in pages:
        try:
            pages[url] = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf8", "ignore")
        except Exception as e:
            print("  fetch failed", url, e, file=sys.stderr); pages[url] = ""
        time.sleep(0.5)
    return pages[url]

shared = {}  # a page used by several places (e.g. one operator page) has no single number
for p in data["places"]:
    if p.get("web"): shared[p["web"]] = shared.get(p["web"], 0) + 1

for p in data["places"]:
    web = p.get("web")
    if not web or (p.get("phone") and not force): continue
    host = urlparse(web).hostname or ""
    if any(s in host for s in SKIP) or shared[web] > 1:
        continue
    nums = []
    for m in re.findall(r'href=["\']tel:([^"\']+)["\']', fetch(web), re.I):
        n = re.sub(r"[^\d+]", "", m)
        if n.startswith("+44"): n = "0" + n[3:]
        if n.startswith("440"): n = n[2:]
        if re.fullmatch(r"0\d{9,10}", n) and n not in nums: nums.append(n)
    if not nums:
        print("no tel: link", p["id"], web, file=sys.stderr); continue
    n = nums[0]
    if n.startswith("02"): pretty = n[:3] + " " + n[3:7] + " " + n[7:]
    elif n.startswith(("01", "07")): pretty = n[:5] + " " + n[5:]
    else: pretty = n[:4] + " " + n[4:]
    p["phone"], p["phoneSource"] = pretty, web
    print("ok", p["id"], pretty, ("(+%d more on page)" % (len(nums) - 1)) if len(nums) > 1 else "", file=sys.stderr)

json.dump(data, open(path, "w"), indent=1, ensure_ascii=False)
