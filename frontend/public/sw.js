// Service worker: satisfies PWA installability (home screen icon, standalone
// launch) and speeds up repeat loads of static assets. Does NOT cache API
// responses at all - an earlier version tried offline viewing of ledger
// data (dashboard/parties/etc while genuinely disconnected), but the
// caching + banner system it required proved unreliable across several
// real attempts to get it right (a stuck banner, a race between multiple
// concurrent requests each independently reporting "online" or "offline"
// with no guaranteed order, resulting in the banner showing even while
// live data was loading correctly). Removed entirely rather than keep
// patching increasing complexity - every API call is now a plain network
// request, full stop. A genuine connection problem now surfaces as the
// app's own honest error message with a retry button (see api.js /
// Dashboard.jsx), not a banner that could show a false state.
//
// IMPORTANT: the HTML page and JS/CSS bundles are network-first, not
// cache-first. Vite fingerprints filenames uniquely on every build, so a
// cached HTML page from an older deploy would reference JS/CSS files that
// no longer exist after the next deploy - a blank white screen. An earlier
// version of this file cached '/' with cache-first and caused exactly that
// bug. Bumping CACHE_NAME forces old, broken caches to be discarded for
// anyone who already got stuck on a stale version.

const CACHE_NAME = 'khata-shell-v3'
const STATIC_ASSETS = ['/manifest.json', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Never intercept API calls or file downloads - always go straight to
  // the network, no caching in either direction. Full stop, no exceptions.
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/files/')) {
    return
  }

  // Navigation requests (the HTML page) and JS/CSS: network first, so a new
  // deploy is picked up immediately, but cache each successful response so
  // there's still something to fall back to if the page shell itself needs
  // reloading with genuinely no connection at all.
  if (event.request.mode === 'navigate' || url.pathname.endsWith('.js') || url.pathname.endsWith('.css')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone()
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone))
          }
          return response
        })
        .catch(() => caches.match(event.request))
    )
    return
  }

  // Small static assets (icons, manifest) can be cache-first - these don't
  // change between deploys the way fingerprinted JS/CSS does.
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  )
})
