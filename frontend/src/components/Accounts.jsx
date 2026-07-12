import { useState, useEffect } from 'react'
import { api, setToken, getDisplayName } from '../api'

export default function Accounts({ onFirstAccountCreated }) {
  const [users, setUsers] = useState(null) // null = not loaded yet
  const [authRequired, setAuthRequired] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)

  function reload() {
    api.getAuthStatus().then((status) => {
      setAuthRequired(status.required)
      if (status.required) {
        api.listUsers().then(setUsers).catch(() => setUsers([]))
      } else {
        setUsers([])
      }
    })
  }

  useEffect(() => {
    reload()
  }, [])

  if (users === null) {
    return <div className="mx-auto max-w-2xl px-4 py-6 text-sm text-ink-faint">Loading…</div>
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Accounts</h1>
        <p className="mt-1 text-sm text-ink-faint">
          {authRequired
            ? 'Everyone has the same access - separate accounts are just so every entry shows who added or changed it.'
            : "No accounts set up yet - the app is fully open. Create the first account below to turn on login."}
        </p>
      </header>

      {!authRequired ? (
        <FirstAccountForm
          onCreated={() => {
            reload()
            onFirstAccountCreated?.()
          }}
        />
      ) : (
        <div className="space-y-4">
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
                  <UserRow key={u.id} user={u} onChanged={reload} totalActive={users.filter((x) => x.is_active).length} />
                ))}
              </tbody>
            </table>
          </div>

          {showAddForm ? (
            <AddUserForm onDone={() => { setShowAddForm(false); reload() }} onCancel={() => setShowAddForm(false)} />
          ) : (
            <button
              onClick={() => setShowAddForm(true)}
              className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper hover:bg-ink-light"
            >
              + Add person
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function UserRow({ user, onChanged, totalActive }) {
  const isYou = user.display_name === getDisplayName()
  const canRemove = user.is_active && !(totalActive <= 1)

  async function remove() {
    if (!confirm(`Remove ${user.display_name}'s access? They'll need a new account to log in again.`)) return
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

function AddUserForm({ onDone, onCancel }) {
  const [form, setForm] = useState({ username: '', display_name: '', password: '' })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function submit() {
    setError(null)
    if (!form.username || !form.display_name || !form.password) {
      setError('All fields are required.')
      return
    }
    setSaving(true)
    try {
      await api.registerUser(form)
      onDone()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-line bg-white p-4">
      {error && <p className="rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}
      <Field label="Their name (shown on their entries)">
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
      <div className="flex gap-2">
        <button
          onClick={submit}
          disabled={saving}
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          {saving ? 'Adding…' : 'Add person'}
        </button>
        <button onClick={onCancel} className="rounded-md border border-line px-4 py-2 text-sm text-ink-faint">
          Cancel
        </button>
      </div>
    </div>
  )
}

function FirstAccountForm({ onCreated }) {
  const [form, setForm] = useState({ username: '', display_name: '', password: '' })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function submit() {
    setError(null)
    if (!form.username || !form.display_name || !form.password) {
      setError('All fields are required.')
      return
    }
    setSaving(true)
    try {
      await api.registerUser(form)
      // Log straight in as the account just created, rather than making
      // someone type their new password twice in a row.
      const result = await api.login(form.username, form.password)
      if (result.token) setToken(result.token, result.display_name)
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
