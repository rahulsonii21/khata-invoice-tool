import { useState, useEffect, useRef } from 'react'
import { api, setToken } from '../api'

export default function Login({ onSuccess }) {
  const [mode, setMode] = useState('login') // 'login' | 'redeem'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [inviteToken, setInviteToken] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [slow, setSlow] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => {
    // A shared invite link can carry ?invite=<token> so it's pre-filled
    // instead of someone having to copy-paste it in manually.
    const params = new URLSearchParams(window.location.search)
    const tokenFromUrl = params.get('invite')
    if (tokenFromUrl) {
      setInviteToken(tokenFromUrl)
      setMode('redeem')
    }
  }, [])

  useEffect(() => () => clearTimeout(timerRef.current), [])

  function startTimers() {
    setError(null)
    setLoading(true)
    setSlow(false)
    // If the request is still pending after 3s, it's very likely a cold
    // Render server waking up (a real 30-60s delay, not a frontend
    // slowdown) - say so honestly instead of leaving a bare spinner.
    timerRef.current = setTimeout(() => setSlow(true), 3000)
  }

  async function handleLogin(e) {
    e.preventDefault()
    startTimers()
    try {
      const result = await api.login(username, password)
      if (result.token) setToken(result.token, result.display_name, result.company_name, result.is_platform_admin)
      onSuccess()
    } catch (e) {
      setError(e.message === 'WRONG_CREDENTIALS' ? 'Incorrect username or password.' : "Couldn't reach the server. Check your connection and try again.")
    } finally {
      clearTimeout(timerRef.current)
      setLoading(false)
      setSlow(false)
    }
  }

  async function handleRedeem(e) {
    e.preventDefault()
    startTimers()
    try {
      await api.registerUser({
        username, display_name: displayName, password,
        invite_token: inviteToken, company_name: companyName || null,
      })
      const result = await api.login(username, password)
      if (result.token) setToken(result.token, result.display_name, result.company_name, result.is_platform_admin)
      onSuccess()
    } catch (e) {
      setError(e.message || 'Something went wrong redeeming that invite.')
    } finally {
      clearTimeout(timerRef.current)
      setLoading(false)
      setSlow(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-xs rounded-lg border border-line bg-white p-6 text-center">
        <span className="stamp mx-auto mb-3 inline-block px-3 py-1 text-sm font-semibold text-ink">लेख</span>
        <h1 className="font-display text-xl font-semibold text-ink">Lekha</h1>
        <p className="mt-1 text-sm text-ink-faint">{mode === 'login' ? 'Log in to continue' : 'Redeem your invite'}</p>

        {mode === 'login' ? (
          <form onSubmit={handleLogin} className="mt-5 space-y-3">
            <input
              type="text" autoFocus autoCapitalize="none" autoCorrect="off"
              value={username} onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
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
              type="submit" disabled={loading || !username || !password}
              className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
            >
              {loading ? 'Checking…' : 'Log in'}
            </button>
            <button type="button" onClick={() => setMode('redeem')} className="text-xs text-ink-faint hover:text-ink">
              Have an invite? Redeem it here
            </button>
          </form>
        ) : (
          <form onSubmit={handleRedeem} className="mt-5 space-y-3 text-left">
            <input
              value={inviteToken} onChange={(e) => setInviteToken(e.target.value)}
              placeholder="Invite code"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
            <input
              value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
            <input
              value={username} onChange={(e) => setUsername(e.target.value)}
              autoCapitalize="none" placeholder="Choose a username"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Choose a password"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
            <input
              value={companyName} onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Company name (only if starting a new one)"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
            {error && <p className="text-sm text-rust">{error}</p>}
            {loading && slow && (
              <p className="text-xs text-marigold">
                Waking up the server — this can take up to a minute if the app hasn't been used in a while.
              </p>
            )}
            <button
              type="submit" disabled={loading || !inviteToken || !displayName || !username || !password}
              className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
            >
              {loading ? 'Setting up…' : 'Create account'}
            </button>
            <button type="button" onClick={() => setMode('login')} className="text-xs text-ink-faint hover:text-ink">
              Already have an account? Log in
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
