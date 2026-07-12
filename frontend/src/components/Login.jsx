import { useState, useEffect, useRef } from 'react'
import { api, setToken } from '../api'

export default function Login({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [slow, setSlow] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => () => clearTimeout(timerRef.current), [])

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    setSlow(false)
    // If the login request is still pending after 3s, it's very likely a
    // cold Render server waking up (a real 30-60s delay, not a frontend
    // slowdown) - say so honestly instead of leaving a bare "Checking…"
    // that looks stuck.
    timerRef.current = setTimeout(() => setSlow(true), 3000)
    try {
      const result = await api.login(username, password)
      if (result.token) setToken(result.token, result.display_name)
      onSuccess()
    } catch (e) {
      if (e.message === 'WRONG_CREDENTIALS') {
        setError('Incorrect username or password.')
      } else {
        setError("Couldn't reach the server. Check your connection and try again.")
      }
    } finally {
      clearTimeout(timerRef.current)
      setLoading(false)
      setSlow(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-xs rounded-lg border border-line bg-white p-6 text-center">
        <span className="stamp mx-auto mb-3 inline-block px-3 py-1 text-sm font-semibold text-ink">खाता</span>
        <h1 className="font-display text-xl font-semibold text-ink">Khata</h1>
        <p className="mt-1 text-sm text-ink-faint">Log in to continue</p>

        <form onSubmit={handleSubmit} className="mt-5 space-y-3">
          <input
            type="text"
            autoFocus
            autoCapitalize="none"
            autoCorrect="off"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username"
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
          />
          {error && <p className="text-sm text-rust">{error}</p>}
          {loading && slow && (
            <p className="text-xs text-marigold">
              Waking up the server — this can take up to a minute if the app hasn't been used in a while.
            </p>
          )}
          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
          >
            {loading ? 'Checking…' : 'Log in'}
          </button>
        </form>
      </div>
    </div>
  )
}
