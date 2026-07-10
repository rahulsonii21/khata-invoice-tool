import { useState, useEffect } from 'react'
import { api } from '../api'

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export default function Reports() {
  const [direction, setDirection] = useState('sales') // 'sales' | 'purchases'
  const [parties, setParties] = useState([])
  const [suppliers, setSuppliers] = useState([])
  const [month, setMonth] = useState(currentMonth())
  const [entityId, setEntityId] = useState('') // '' = everyone
  const [downloading, setDownloading] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listParties().then(setParties).catch(() => {})
    api.listSuppliers().then(setSuppliers).catch(() => {})
  }, [])

  // Reset the entity selection when switching direction, since a party id
  // and a supplier id aren't interchangeable
  useEffect(() => {
    setEntityId('')
  }, [direction])

  async function handleDownload(kind, fn) {
    setError(null)
    setDownloading(kind)
    try {
      await fn(month, entityId || null)
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

  const entities = direction === 'sales' ? parties : suppliers
  const entityLabel = direction === 'sales' ? 'Party' : 'Supplier'
  const entityAllLabel = direction === 'sales' ? 'All parties' : 'All suppliers'

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Reports</h1>
        <p className="mt-1 text-sm text-ink-faint">
          Month-wise reports and bill exports, for one party/supplier or your whole business.
        </p>
      </header>

      <div className="mb-4 inline-flex rounded-md border border-line bg-white p-1">
        <button
          onClick={() => setDirection('sales')}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            direction === 'sales' ? 'bg-ink text-paper' : 'text-ink-faint'
          }`}
        >
          Sales (customers)
        </button>
        <button
          onClick={() => setDirection('purchases')}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            direction === 'purchases' ? 'bg-ink text-paper' : 'text-ink-faint'
          }`}
        >
          Purchases (suppliers)
        </button>
      </div>

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
            <span className="mb-1 block text-xs font-medium text-ink-faint">{entityLabel}</span>
            <select
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            >
              <option value="">{entityAllLabel}</option>
              {entities.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="text-xs text-ink-faint">
          Showing options for <span className="font-medium text-ink">{monthLabel}</span>
          {entityId && (
            <> — <span className="font-medium text-ink">{entities.find((e) => e.id === entityId)?.name}</span></>
          )}
        </p>

        {direction === 'sales' ? (
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
        ) : (
          <div className="space-y-2 border-t border-line pt-4">
            <ReportButton
              title="Summary PDF"
              description="Totals per supplier for the month, with a grand total at the top."
              downloading={downloading === 'summary'}
              onClick={() => handleDownload('summary', api.downloadMonthlyPurchaseSummaryPdf)}
            />
            <ReportButton
              title="Detailed Excel"
              description="Every purchase and payment for the month, row by row."
              downloading={downloading === 'detail'}
              onClick={() => handleDownload('detail', api.downloadMonthlyPurchaseDetailedExcel)}
            />
            <ReportButton
              title="Combined Bills PDF"
              description="Every supplier bill photo for the month, merged into one PDF in date order."
              downloading={downloading === 'bills'}
              onClick={() => handleDownload('bills', api.downloadMonthlyPurchaseBillsPdf)}
            />
          </div>
        )}
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
