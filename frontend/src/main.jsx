import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

if ('serviceWorker' in navigator) {
  // Different open tabs/devices could otherwise get stuck running whatever
  // service worker version happened to be live when each one first
  // installed it - browsers don't aggressively re-check for a newer sw.js
  // on their own, so two people could genuinely be running different,
  // out-of-date caching logic at the same time with no way to tell. This
  // makes every tab converge on the latest version as reliably as possible:
  // check for updates immediately and again periodically, and once a new
  // version actually takes control, reload automatically so the page is
  // always running the matching, current JavaScript rather than old code
  // left over in memory from before the update.
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then((registration) => {
      registration.update()
      setInterval(() => registration.update(), 60 * 60 * 1000)
    }).catch(() => {})
  })

  let reloading = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading) return
    reloading = true
    window.location.reload()
  })
}
