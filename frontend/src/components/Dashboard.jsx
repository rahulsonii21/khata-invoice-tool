import { useEffect, useState } from 'react'
import { api } from '../api'
import { formatINR, STATUS_STYLES } from '../utils'

export default function Dashboard({ onOpenParty, onOpenSupplier }) {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  function load() {
    setError(null)
    api.getSummary().then(setSummary).catch((e) => setError(e.message))
  }

  useEffect(() => {
    load()
  }, [])

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-6 text-center">
        <p className="text-sm text-rust">{error}</p>
        <button
          onClick={load}
          className="mt-3 rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-sage"
        >
          Try again
        </button>
      </div>
    )
  }
  if (!summary) return <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-ink-faint">Loading…</div>

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Dashboard</h1>
        <p className="mt-1 text-sm text-ink-faint">Everything owed, at a glance.</p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatCard label="Total invoiced" value={summary.total_invoiced} />
        <StatCard label="Total received" value={summary.total_received} tone="ink-light" />
        <StatCard label="Outstanding" value={summary.total_outstanding} tone="rust" />
        <StatCard label="Overdue" value={summary.total_overdue} tone="rust" sublabel={`${summary.overdue_count} invoice${summary.overdue_count !== 1 ? 's' : ''}`} />
      </div>

      {summary.top_overdue_parties?.length > 0 && (
        <section className="mt-6 rounded-lg border border-rust/30 bg-rust/5 p-4">
          <h2 className="font-display text-base font-semibold text-rust">Needs follow-up (overdue)</h2>
          <ul className="mt-3 space-y-2">
            {summary.top_overdue_parties.map((p) => (
              <li
                key={p.party_id}
                onClick={() => onOpenParty(p.party_id)}
                className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-white"
              >
                <span className="text-ink">{p.name} <span className="text-xs text-ink-faint">({p.count} overdue)</span></span>
                <span className="tabular-nums font-medium text-rust">{formatINR(p.amount)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Payables - what THIS business owes suppliers, kept visually distinct
          from receivables above so the two directions of money never get
          confused with each other at a glance. */}
      {summary.supplier_count > 0 && (
        <section className="mt-6 rounded-lg border border-line bg-white p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-base font-semibold text-ink">You owe suppliers</h2>
            <span className="tabular-nums font-display text-lg font-semibold text-marigold">
              {formatINR(summary.total_payable)}
            </span>
          </div>
          {summary.total_payable_overdue > 0 && (
            <p className="mt-1 text-xs text-rust">
              {formatINR(summary.total_payable_overdue)} of that is overdue ({summary.payable_overdue_count})
            </p>
          )}
          <ul className="mt-3 space-y-2">
            {summary.top_payable_suppliers?.length === 0 && (
              <li className="text-sm text-ink-faint">Nothing payable — all clear.</li>
            )}
            {summary.top_payable_suppliers?.map((s) => (
              <li
                key={s.supplier_id}
                onClick={() => onOpenSupplier?.(s.supplier_id)}
                className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-sage"
              >
                <span className="text-ink">{s.name}</span>
                <span className="tabular-nums font-medium text-marigold">{formatINR(s.outstanding)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        <section className="rounded-lg border border-line bg-white p-4">
          <h2 className="font-display text-base font-semibold text-ink">Top outstanding</h2>
          <ul className="mt-3 space-y-2">
            {summary.top_outstanding_parties.length === 0 && (
              <li className="text-sm text-ink-faint">Nothing outstanding — all clear.</li>
            )}
            {summary.top_outstanding_parties.map((p) => (
              <li
                key={p.party_id}
                onClick={() => onOpenParty(p.party_id)}
                className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-sage"
              >
                <span className="text-ink">{p.name}</span>
                <span className="tabular-nums font-medium text-rust">{formatINR(p.outstanding)}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-lg border border-line bg-white p-4">
          <h2 className="font-display text-base font-semibold text-ink">Recent payments</h2>
          <ul className="mt-3 space-y-2">
            {summary.recent_payments.length === 0 && (
              <li className="text-sm text-ink-faint">No payments logged yet.</li>
            )}
            {summary.recent_payments.map((p) => (
              <li key={p.id} className="flex items-center justify-between px-2 py-2 text-sm">
                <span className="text-ink">{p.party_name}</span>
                <span className="tabular-nums font-medium text-ink-light">{formatINR(p.amount)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="mt-6 rounded-lg border border-line bg-white p-4">
        <h2 className="font-display text-base font-semibold text-ink">Recent invoices</h2>
        <ul className="mt-3 divide-y divide-line">
          {summary.recent_invoices.length === 0 && (
            <li className="py-2 text-sm text-ink-faint">No invoices uploaded yet.</li>
          )}
          {summary.recent_invoices.map((inv) => {
            const s = inv.is_overdue ? STATUS_STYLES.overdue : (STATUS_STYLES[inv.status] || STATUS_STYLES.unpaid)
            return (
              <li key={inv.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <span className="text-ink">{inv.party_name}</span>
                  {inv.invoice_number && (
                    <span className="ml-2 text-xs text-ink-faint">#{inv.invoice_number}</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="tabular-nums text-ink">{formatINR(inv.amount)}</span>
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${s.className}`}>{s.label}</span>
                </div>
              </li>
            )
          })}
        </ul>
      </section>
    </div>
  )
}

function StatCard({ label, value, tone = 'ink', sublabel }) {
  const toneClass = { ink: 'text-ink', 'ink-light': 'text-ink-light', rust: 'text-rust' }[tone]
  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <p className="text-xs font-medium text-ink-faint">{label}</p>
      <p className={`mt-1 font-display text-2xl font-semibold tabular-nums ${toneClass}`}>
        {formatINR(value)}
      </p>
      {sublabel && <p className="mt-0.5 text-xs text-ink-faint">{sublabel}</p>}
    </div>
  )
}
