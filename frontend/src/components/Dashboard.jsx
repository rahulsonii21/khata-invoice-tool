import { useEffect, useState } from 'react'
import { api } from '../api'
import { formatINR, STATUS_STYLES } from '../utils'

export default function Dashboard({ onOpenParty }) {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getSummary().then(setSummary).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-rust">{error}</div>
  if (!summary) return <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-ink-faint">Loading…</div>

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Dashboard</h1>
        <p className="mt-1 text-sm text-ink-faint">Everything owed, at a glance.</p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Total invoiced" value={summary.total_invoiced} />
        <StatCard label="Total received" value={summary.total_received} tone="ink-light" />
        <StatCard label="Outstanding" value={summary.total_outstanding} tone="rust" />
      </div>

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
            const s = STATUS_STYLES[inv.status] || STATUS_STYLES.unpaid
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

function StatCard({ label, value, tone = 'ink' }) {
  const toneClass = { ink: 'text-ink', 'ink-light': 'text-ink-light', rust: 'text-rust' }[tone]
  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <p className="text-xs font-medium text-ink-faint">{label}</p>
      <p className={`mt-1 font-display text-2xl font-semibold tabular-nums ${toneClass}`}>
        {formatINR(value)}
      </p>
    </div>
  )
}
