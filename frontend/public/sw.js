// Minimal service worker - primarily exists to satisfy PWA installability
// criteria (Chrome requires an active service worker with a fetch handler).
// Deliberately NOT attempting real offline data caching - this app's data
// comes from a live API, and serving stale cached API responses would be
// actively misleading for a bookkeeping tool. Static assets get a light
// cache-first treatment; everything else just passes through to the network.

const CACHE_NAME = 'khata-shell-v1'
const SHELL_ASSETS = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)).catch(() => {})
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

  // Cache-first for the static app shell itself
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  )
})
