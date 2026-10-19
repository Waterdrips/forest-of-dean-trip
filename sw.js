// Offline support: the page and its data come from the network when there's signal (so updates show at
// once) and from the cache when there isn't, or when the network takes more than 4 seconds. Photos and Leaflet are cached as they're viewed,
// or all at once with "Save for offline". Map tiles are kept for a week as they're viewed. The weather isn't cached here
// (the page keeps its own copy of the last forecast).
const VERSION = "planner-v5";
const KEEP = [VERSION, "planner-offline", "planner-tiles"];  // "Save for offline" fills planner-offline; viewed map tiles go in planner-tiles
const SHELL = ["./", "index.html", "data.json", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => !KEEP.includes(k)).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

// this version's cache first, then anything "Save for offline" kept
const lookup = (cache, key) => cache.match(key, {ignoreSearch: true}).then(hit => hit || caches.match(key, {ignoreSearch: true}));

function staleWhileRevalidate(req, cacheKey) {
  return caches.open(VERSION).then(cache => lookup(cache, cacheKey || req).then(hit => {
    const fresh = fetch(req).then(res => { if (res.ok) cache.put(cacheKey || req, res.clone()); return res; }).catch(() => hit);
    return hit || fresh;
  }));
}

// Map tiles: from the phone if seen in the last week, otherwise the network (falling back to an older copy offline).
function tile(req) {
  return caches.open("planner-tiles").then(cache => cache.match(req).then(hit => {
    const age = hit ? Date.now() - new Date(hit.headers.get("date") || 0) : Infinity;
    if (hit && age < 7 * 864e5) return hit;
    return fetch(req).then(res => { if (res.ok || res.type === "opaque") cache.put(req, res.clone()); return res; }).catch(() => hit || Response.error());
  }));
}

function networkFirst(req, cacheKey) {
  return caches.open(VERSION).then(cache => {
    const fromCache = () => lookup(cache, cacheKey || req);
    const net = fetch(req).then(res => { if (res.ok) cache.put(cacheKey || req, res.clone()); return res; });
    const timeout = new Promise(res => setTimeout(res, 4000)).then(fromCache);
    return Promise.race([net.catch(fromCache), timeout.then(hit => hit || net)]).then(r => r || net);
  });
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.searchParams.has("_check")) return;  // the page's own "is there a newer version?" check
  if (url.origin === location.origin) {
    // Navigations (including shared links with ?s=...) all get the cached page.
    if (req.mode === "navigate") return e.respondWith(networkFirst(req, new URL("index.html", self.registration.scope).href));
    if (url.pathname.endsWith("/data.json")) return e.respondWith(networkFirst(req));
    return e.respondWith(staleWhileRevalidate(req));
  }
  if (url.hostname === "cdnjs.cloudflare.com" || url.hostname.endsWith("wikimedia.org")) {
    e.respondWith(staleWhileRevalidate(req));
  } else if (url.hostname.endsWith("tile.openstreetmap.org")) {
    e.respondWith(tile(req));
  }
});
