import { useState, useEffect } from 'react'
import { api } from '../api'

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export default function Reports() {
  const [parties, setParties] = useState([])
  const [month, setMonth] = useState(currentMonth())
  const [partyId, setPartyId] = useState('') // '' = all parties
  const [downloading, setDownloading] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listParties().then(setParties).catch(() => {})
  }, [])

  async function handleDownload(kind, fn) {
    setError(null)
    setDownloading(kind)
    try {
      await fn(month, partyId || null)
    } catch (e) {
      setError(e.message)
    } finally {
      setDownloading(null)
    }
  }

  const monthLabel = (() => {
    const [y, m] = month.split('-')
    return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
  })()

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Reports</h1>
        <p className="mt-1 text-sm text-ink-faint">
          Month-wise sales reports and bill exports, for one party or your whole business.
        </p>
      </header>

      {error && <p className="mb-4 rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}

      <div className="space-y-4 rounded-lg border border-line bg-white p-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-faint">Month</span>
            <input
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-ink-faint">Party</span>
            <select
              value={partyId}
              onChange={(e) => setPartyId(e.target.value)}
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            >
              <option value="">All parties</option>
              {parties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="text-xs text-ink-faint">
          Showing options for <span className="font-medium text-ink">{monthLabel}</span>
          {partyId && (
            <> — <span className="font-medium text-ink">{parties.find((p) => p.id === partyId)?.name}</span></>
          )}
        </p>

        <div className="space-y-2 border-t border-line pt-4">
          <ReportButton
            title="Summary PDF"
            description="Totals per party for the month, with a grand total at the top."
            downloading={downloading === 'summary'}
            onClick={() => handleDownload('summary', api.downloadMonthlySummaryPdf)}
          />
          <ReportButton
            title="Detailed Excel"
            description="Every invoice and payment for the month, row by row."
            downloading={downloading === 'detail'}
            onClick={() => handleDownload('detail', api.downloadMonthlyDetailedExcel)}
          />
          <ReportButton
            title="Combined Bills PDF"
            description="Every bill photo and generated bill for the month, merged into one PDF in date order."
            downloading={downloading === 'bills'}
            onClick={() => handleDownload('bills', api.downloadMonthlyBillsPdf)}
          />
        </div>
      </div>
    </div>
  )
}

function ReportButton({ title, description, downloading, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={downloading}
      className="flex w-full items-center justify-between rounded-md border border-line px-4 py-3 text-left hover:bg-sage/30 disabled:opacity-50"
    >
      <div>
        <p className="text-sm font-medium text-ink">{title}</p>
        <p className="text-xs text-ink-faint">{description}</p>
      </div>
      <span className="text-xs font-medium text-ink-light">{downloading ? 'Downloading…' : 'Download'}</span>
    </button>
  )
}
