// Offline support: the page and its data are served from cache when there's no signal and refreshed in
// the background when there is. Photos and Leaflet are cached as they're viewed. Map tiles and the
// weather aren't cached here (the page keeps its own copy of the last forecast).
const VERSION = "planner-v2";
const SHELL = ["./", "index.html", "data.json", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

function staleWhileRevalidate(req, cacheKey) {
  return caches.open(VERSION).then(cache => cache.match(cacheKey || req, {ignoreSearch: true}).then(hit => {
    const fresh = fetch(req).then(res => { if (res.ok) cache.put(cacheKey || req, res.clone()); return res; }).catch(() => hit);
    return hit || fresh;
  }));
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    // Navigations (including shared links with ?s=...) all get the cached page.
    if (req.mode === "navigate") return e.respondWith(staleWhileRevalidate(req, new URL("index.html", self.registration.scope).href));
    return e.respondWith(staleWhileRevalidate(req));
  }
  if (url.hostname === "cdnjs.cloudflare.com" || url.hostname.endsWith("wikimedia.org")) {
    e.respondWith(staleWhileRevalidate(req));
  }
});
