// Minimal service worker - primarily exists to satisfy PWA installability
// criteria (Chrome requires an active service worker with a fetch handler).
//
// IMPORTANT: the HTML page must be network-first, not cache-first. Vite
// fingerprints JS/CSS filenames uniquely on every build, so a cached HTML
// page from an older deploy will reference asset files that no longer
// exist after the next deploy - which shows up as a blank white screen,
// since the browser can't find the JS bundle the (stale) HTML asks for.
// A previous version of this file cached '/' with cache-first and caused
// exactly that. Bumping CACHE_NAME also forces old, broken caches to be
// discarded for anyone who already got stuck on a stale version.

const CACHE_NAME = 'khata-shell-v2'
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

  // Never intercept API calls - always go to the network for live data
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/files/')) {
    return
  }

  // Navigation requests (the HTML page itself) and JS/CSS: always try the
  // network first, so a new deploy is picked up immediately. Only fall back
  // to cache if genuinely offline.
  if (event.request.mode === 'navigate' || url.pathname.endsWith('.js') || url.pathname.endsWith('.css')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    )
    return
  }

  // Small static assets (icons, manifest) can be cache-first - these don't
  // change between deploys the way fingerprinted JS/CSS does.
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  )
})
