# Usage: python3 -I tools/photos.py data.json [--force]
# Each place's "photo" field names an English Wikipedia article (e.g. "Tintern Abbey"). This fetches that
# article's lead image, keeps it only if it's freely licensed on Wikimedia Commons, and stores the image URL
# and full credit (artist, licence, licence link, file page) in data["photos"]. Places whose article has no
# free image get their "photo" removed. Requests are batched (40 titles) and back off when rate-limited.
import json, re, sys, time, html, urllib.request, urllib.parse, urllib.error

UA = {"User-Agent": "holiday-planner/1.0 (personal trip page)"}
path = sys.argv[1]; force = "--force" in sys.argv
data = json.load(open(path))
photos = data.setdefault("photos", {})

def get(url, params):
    for i in range(5):
        try:
            u = url + "?" + urllib.parse.urlencode(params)
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(10 * (i + 1)); continue
            raise
    raise SystemExit("Wikimedia kept rate-limiting; try again in a few minutes")

strip = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()
def clean_artist(a):
    a = strip(a) or "Unknown author"
    a = re.sub(r"(Unknown author)+", "Unknown author", a)
    a = re.sub(r"\s*\(talk\)", "", a)
    return re.sub(r"^The original uploader was (\S+) at (\w+) Wikipedia.*$", r"\1 (\2 Wikipedia)", a)

wanted = sorted({p["photo"] for p in data["places"] if p.get("photo") and (force or p["photo"] not in photos)})
pages, back = {}, {}
for n in range(0, len(wanted), 40):
    q = get("https://en.wikipedia.org/w/api.php", {"action": "query", "titles": "|".join(wanted[n:n+40]), "prop": "pageimages|info",
            "piprop": "name", "inprop": "url", "redirects": 1, "format": "json"})["query"]
    for k in ("normalized", "redirects"):
        for x in q.get(k, []): back[x["to"]] = back.get(x["from"], x["from"])
    for pg in q["pages"].values():
        if "pageimage" in pg: pages[back.get(pg["title"], pg["title"])] = (pg["pageimage"], pg["fullurl"])
    time.sleep(2)

files = sorted({"File:" + v[0] for v in pages.values()})
info = {}
for n in range(0, len(files), 40):
    q = get("https://commons.wikimedia.org/w/api.php", {"action": "query", "titles": "|".join(files[n:n+40]), "prop": "imageinfo",
            "iiprop": "url|extmetadata", "iiurlwidth": 800, "format": "json"})["query"]
    norm = {x["to"]: x["from"] for x in q.get("normalized", [])}
    for cp in q["pages"].values():
        if "imageinfo" not in cp: continue  # not on Commons (e.g. a non-free local file): never use it
        ii = cp["imageinfo"][0]; m = ii.get("extmetadata", {})
        lic = strip(m.get("LicenseShortName", {}).get("value"))
        if not re.search(r"\bcc\b|cc-|cc0|public domain|pd", lic, re.I): continue
        rec = {"img": ii["thumburl"].split("?")[0], "page": ii["descriptionurl"], "artist": clean_artist(m.get("Artist", {}).get("value")),
               "license": lic, "licenseUrl": m.get("LicenseUrl", {}).get("value", "")}
        info[cp["title"]] = rec; info[norm.get(cp["title"], cp["title"])] = rec
    time.sleep(2)

for t in wanted:
    if t in pages:
        rec = info.get("File:" + pages[t][0].replace("_", " ")) or info.get("File:" + pages[t][0])
        if rec:
            photos[t] = dict(rec, title=t, wiki=pages[t][1]); print("ok", t, "|", rec["license"], "|", rec["artist"][:40], file=sys.stderr); continue
    print("no free photo:", t, file=sys.stderr)

for p in data["places"]:
    if p.get("photo") and p["photo"] not in photos: p.pop("photo")
json.dump(data, open(path, "w"), indent=1, ensure_ascii=False)
