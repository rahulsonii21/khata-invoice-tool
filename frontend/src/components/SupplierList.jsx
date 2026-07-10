import { useEffect, useState } from 'react'
import { api } from '../api'
import { formatINR } from '../utils'

export default function SupplierList({ onOpenSupplier }) {
  const [suppliers, setSuppliers] = useState([])
  const [query, setQuery] = useState('')
  const [showNewForm, setShowNewForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [newGstin, setNewGstin] = useState('')

  function reload() {
    api.listSuppliers().then(setSuppliers).catch(() => {})
  }

  useEffect(() => {
    reload()
  }, [])

  async function handleCreate() {
    if (!newName.trim()) return
    await api.createSupplier({ name: newName.trim(), gstin: newGstin.trim() || null })
    setNewName('')
    setNewGstin('')
    setShowNewForm(false)
    reload()
  }

  const filtered = suppliers.filter((s) => s.name.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Suppliers</h1>
          <p className="mt-1 text-sm text-ink-faint">What you owe, supplier by supplier.</p>
        </div>
        <button
          onClick={() => setShowNewForm((s) => !s)}
          className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper hover:bg-ink-light"
        >
          + New supplier
        </button>
      </header>

      {showNewForm && (
        <div className="mb-4 flex gap-2 rounded-lg border border-line bg-white p-3">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Supplier name"
            className="flex-1 rounded-md border border-line px-3 py-2 text-sm"
          />
          <input
            value={newGstin}
            onChange={(e) => setNewGstin(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="GSTIN (optional)"
            className="w-48 rounded-md border border-line px-3 py-2 text-sm"
          />
          <button
            onClick={handleCreate}
            className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light"
          >
            Add
          </button>
        </div>
      )}

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search suppliers…"
        className="mb-4 w-full rounded-md border border-line bg-white px-3 py-2 text-sm"
      />

      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-sage/40 text-left text-xs font-medium text-ink-faint">
              <th className="px-4 py-2">Supplier</th>
              <th className="px-4 py-2">GSTIN</th>
              <th className="px-4 py-2 text-right">Purchased</th>
              <th className="px-4 py-2 text-right">Paid</th>
              <th className="px-4 py-2 text-right">Payable</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-ink-faint">
                  No suppliers yet.
                </td>
              </tr>
            )}
            {filtered.map((s) => (
              <tr
                key={s.id}
                onClick={() => onOpenSupplier(s.id)}
                className="cursor-pointer border-b border-line last:border-0 hover:bg-sage/30"
              >
                <td className="px-4 py-3 font-medium text-ink">{s.name}</td>
                <td className="px-4 py-3 text-xs text-ink-faint">{s.gstin || '—'}</td>
                <td className="px-4 py-3 text-right tabular-nums text-ink">{formatINR(s.total_purchased)}</td>
                <td className="px-4 py-3 text-right tabular-nums text-ink-light">
                  {formatINR(s.total_paid)}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums font-medium ${
                    s.outstanding > 0 ? 'text-rust' : 'text-ink-light'
                  }`}
                >
                  {formatINR(s.outstanding)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
