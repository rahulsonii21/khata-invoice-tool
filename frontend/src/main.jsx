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
  // on their own. Checking for updates aggressively (immediately on load,
  // and hourly after) closes that gap safely: the actual page content is
  // already always fetched fresh from the network first (see sw.js), so
  // getting the newer SW installed promptly is what matters, not forcing
  // an immediate takeover.
  //
  // Deliberately NOT auto-reloading the page when a new service worker
  // takes control. An earlier version of this did that, and it introduced
  // a real, hard-to-diagnose bug: reloading the page aborts whatever
  // request is currently in flight, and the Dashboard's very own first
  // data fetch on open was exactly the kind of request that could get
  // caught by that timing, right as a fresh service worker take-over
  // happened - it looked like a random, intermittent "failed to fetch"
  // with no clear pattern, until it was traced back to this. Simply
  // getting the update installed (which happens automatically) means the
  // NEXT normal open already has it, without needing to force a
  // disruptive reload during the current one.
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then((registration) => {
      registration.update()
      setInterval(() => registration.update(), 60 * 60 * 1000)
    }).catch(() => {})
  })
}
