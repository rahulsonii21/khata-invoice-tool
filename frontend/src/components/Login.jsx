import { useState } from 'react'
import { api, setToken } from '../api'

export default function Login({ onSuccess }) {
  const [pin, setPin] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await api.login(pin)
      if (result.token) setToken(result.token)
      onSuccess()
    } catch (e) {
      setError('Incorrect PIN. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-xs rounded-lg border border-line bg-white p-6 text-center">
        <span className="stamp mx-auto mb-3 inline-block px-3 py-1 text-sm font-semibold text-ink">खाता</span>
        <h1 className="font-display text-xl font-semibold text-ink">Khata</h1>
        <p className="mt-1 text-sm text-ink-faint">Enter your PIN to continue</p>

        <form onSubmit={handleSubmit} className="mt-5 space-y-3">
          <input
            type="password"
            inputMode="numeric"
            autoFocus
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="PIN"
            className="w-full rounded-md border border-line px-3 py-2 text-center text-lg tracking-widest"
          />
          {error && <p className="text-sm text-rust">{error}</p>}
          <button
            type="submit"
            disabled={loading || !pin}
            className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
          >
            {loading ? 'Checking…' : 'Unlock'}
          </button>
        </form>
      </div>
    </div>
  )
}
