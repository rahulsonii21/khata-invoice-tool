import { useState, useEffect } from 'react'
import { api, setToken, getDisplayName, getCompanyName, getIsPlatformAdmin } from '../api'

export default function Accounts({ onFirstAccountCreated }) {
  const [users, setUsers] = useState(null) // null = not loaded yet
  const [invites, setInvites] = useState([])
  const [authRequired, setAuthRequired] = useState(false)
  const [generating, setGenerating] = useState(null) // 'company' | 'invite' | null

  function reload() {
    api.getAuthStatus().then((status) => {
      setAuthRequired(status.required)
      if (status.required) {
        api.listUsers().then(setUsers).catch(() => setUsers([]))
        api.listInvites().then(setInvites).catch(() => setInvites([]))
      } else {
        setUsers([])
      }
    })
  }

  useEffect(() => {
    reload()
  }, [])

  async function generateInvite(forNewCompany) {
    setGenerating(forNewCompany ? 'company' : 'invite')
    try {
      await api.createInvite(forNewCompany)
      reload()
    } catch (e) {
      alert(e.message)
    } finally {
      setGenerating(null)
    }
  }

  if (users === null) {
    return <div className="mx-auto max-w-2xl px-4 py-6 text-sm text-ink-faint">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Accounts</h1>
        <p className="mt-1 text-sm text-ink-faint">
          {authRequired
            ? `Everyone in ${getCompanyName() || 'your company'} has the same access - separate accounts are just so every entry shows who added or changed it.`
            : "No accounts set up yet - the app is fully open. Create the first one below to turn on login."}
        </p>
      </header>

      {!authRequired ? (
        <FirstAccountForm onCreated={() => { reload(); onFirstAccountCreated?.() }} />
      ) : (
        <div className="space-y-6">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-ink">People in {getCompanyName() || 'your company'}</h2>
            <div className="overflow-hidden rounded-lg border border-line bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line bg-sage/40 text-left text-xs font-medium text-ink-faint">
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Username</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <UserRow key={u.id} user={u} totalActive={users.filter((x) => x.is_active).length} onChanged={reload} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-sm font-semibold text-ink">Invite someone to {getCompanyName() || 'your company'}</h2>
            <p className="mb-2 text-xs text-ink-faint">
              They'll get full access to the same data as everyone else here.
            </p>
            <button
              onClick={() => generateInvite(false)}
              disabled={generating === 'invite'}
              className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
            >
              {generating === 'invite' ? 'Generating…' : '+ Generate invite link'}
            </button>
          </div>

          {getIsPlatformAdmin() && (
            <div className="rounded-lg border border-marigold/40 bg-marigold/5 p-4">
              <h2 className="mb-1 text-sm font-semibold text-ink">Start a brand new, separate business</h2>
              <p className="mb-2 text-xs text-ink-faint">
                Platform admin only. This invite lets someone set up a totally separate company in this same app -
                their data will be completely isolated from {getCompanyName() || 'yours'}.
              </p>
              <button
                onClick={() => generateInvite(true)}
                disabled={generating === 'company'}
                className="rounded-md bg-marigold px-3 py-2 text-sm font-medium text-white hover:bg-marigold/90 disabled:opacity-50"
              >
                {generating === 'company' ? 'Generating…' : '+ Generate new-company invite'}
              </button>
            </div>
          )}

          {invites.length > 0 && (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-ink">Invite links you've created</h2>
              <div className="space-y-2">
                {invites.map((inv) => (
                  <InviteRow key={inv.id} invite={inv} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function UserRow({ user, totalActive, onChanged }) {
  const isYou = user.display_name === getDisplayName()
  const canRemove = user.is_active && totalActive > 1

  async function remove() {
    if (!confirm(`Remove ${user.display_name}'s access? They'll need a new invite to log in again.`)) return
    try {
      await api.deactivateUser(user.id)
      onChanged()
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-4 py-3 text-ink">
        {user.display_name} {isYou && <span className="text-xs text-ink-faint">(you)</span>}
        {!user.is_active && <span className="ml-2 rounded bg-sage px-1.5 py-0.5 text-xs text-ink-faint">Removed</span>}
      </td>
      <td className="px-4 py-3 text-ink-faint">{user.username}</td>
      <td className="px-4 py-3 text-right">
        {canRemove && (
          <button onClick={remove} className="text-xs font-medium text-rust hover:underline">
            Remove
          </button>
        )}
      </td>
    </tr>
  )
}

function InviteRow({ invite }) {
  const [copied, setCopied] = useState(false)
  const link = `${window.location.origin}?invite=${invite.token}`

  function copy() {
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="flex items-center justify-between rounded-md border border-line bg-white px-3 py-2 text-sm">
      <div>
        <span className={invite.used_at ? 'text-ink-faint line-through' : 'text-ink'}>
          {invite.company_id ? 'Join your company' : 'Start new company'}
        </span>
        {invite.used_at && <span className="ml-2 text-xs text-ink-faint">(used)</span>}
      </div>
      {!invite.used_at && (
        <button onClick={copy} className="text-xs font-medium text-ink-light hover:text-ink">
          {copied ? 'Copied!' : 'Copy link'}
        </button>
      )}
    </div>
  )
}

function FirstAccountForm({ onCreated }) {
  const [form, setForm] = useState({ username: '', display_name: '', password: '', company_name: '' })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function submit() {
    setError(null)
    if (!form.username || !form.display_name || !form.password || !form.company_name) {
      setError('All fields are required.')
      return
    }
    setSaving(true)
    try {
      await api.registerUser(form)
      const result = await api.login(form.username, form.password)
      if (result.token) setToken(result.token, result.display_name, result.company_name, result.is_platform_admin)
      onCreated()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-line bg-white p-4">
      {error && <p className="rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}
      <Field label="Your company name">
        <input
          value={form.company_name}
          onChange={(e) => setForm({ ...form, company_name: e.target.value })}
          className="w-full rounded-md border border-line px-3 py-2 text-sm"
        />
      </Field>
      <Field label="Your name">
        <input
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          className="w-full rounded-md border border-line px-3 py-2 text-sm"
        />
      </Field>
      <Field label="Username (for logging in)">
        <input
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          autoCapitalize="none"
          className="w-full rounded-md border border-line px-3 py-2 text-sm"
        />
      </Field>
      <Field label="Password">
        <input
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          className="w-full rounded-md border border-line px-3 py-2 text-sm"
        />
      </Field>
      <button
        onClick={submit}
        disabled={saving}
        className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
      >
        {saving ? 'Setting up…' : 'Create account & turn on login'}
      </button>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-faint">{label}</span>
      {children}
    </label>
  )
}
