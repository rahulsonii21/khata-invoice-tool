// Service worker: satisfies PWA installability, and provides read-only
// offline viewing of ledger data (dashboard, parties, invoices, suppliers,
// purchases) when there's genuinely no network. Writes are never cached or
// queued offline - only real reads, since acting on stale financial data
// offline would be worse than just telling the user to wait for a signal.
//
// IMPORTANT: the HTML page and JS/CSS bundles are network-first, not
// cache-first. Vite fingerprints filenames uniquely on every build, so a
// cached HTML page from an older deploy would reference JS/CSS files that
// no longer exist after the next deploy - a blank white screen. An earlier
// version of this file cached '/' with cache-first and caused exactly that
// bug. Bumping CACHE_NAME forces old, broken caches to be discarded for
// anyone who already got stuck on a stale version.

const CACHE_NAME = 'khata-shell-v2'
const API_CACHE_NAME = 'khata-api-cache-v1'
const STATIC_ASSETS = ['/manifest.json', '/icon-192.png', '/icon-512.png']

// Only GET endpoints that are pure reads get cached for offline viewing.
const CACHEABLE_API_PATTERNS = [
  /^\/api\/dashboard\/summary/,
  /^\/api\/parties(\/|$|\?)/,
  /^\/api\/invoices(\/|$|\?)/,
  /^\/api\/suppliers(\/|$|\?)/,
  /^\/api\/purchases(\/|$|\?)/,
]

function isCacheableApiGet(request, url) {
  return request.method === 'GET' && CACHEABLE_API_PATTERNS.some((p) => p.test(url.pathname + url.search))
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS)).catch(() => {})
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME && k !== API_CACHE_NAME).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Read-only API data: network first, cache fallback only if the network
  // genuinely fails. The frontend shows a banner whenever the fallback is
  // used, so stale data is never mistaken for current.
  if (isCacheableApiGet(event.request, url)) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone()
            caches.open(API_CACHE_NAME).then((cache) => cache.put(event.request, clone))
          }
          return response
        })
        .catch(() =>
          caches.match(event.request).then((cached) => {
            if (!cached) throw new Error('Offline and no cached data available for this request')
            const headers = new Headers(cached.headers)
            headers.set('X-Served-From-Cache', 'true')
            return cached.blob().then((body) => new Response(body, { status: cached.status, headers }))
          })
        )
    )
    return
  }

  // Never intercept other API calls (writes, uploads, OCR, etc.) - always
  // go straight to the network, no caching, no offline fallback. A stale
  // cached response to a write endpoint would be actively dangerous.
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/files/')) {
    return
  }

  // Navigation requests (the HTML page) and JS/CSS: network first, so a new
  // deploy is picked up immediately, but cache each successful response so
  // there's actually something to fall back to if offline later.
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
