import { useEffect, useState } from 'react'
import { api } from '../api'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatWhen(iso) {
  const d = new Date(iso)
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function Backups() {
  const [backups, setBackups] = useState([])
  const [running, setRunning] = useState(false)

  function reload() {
    api.listBackups().then(setBackups).catch(() => {})
  }

  useEffect(() => {
    reload()
  }, [])

  async function handleRunNow() {
    setRunning(true)
    try {
      await api.runBackupNow()
      reload()
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Backups</h1>
          <p className="mt-1 text-sm text-ink-faint">
            Runs automatically every night. The last 14 are kept.
          </p>
        </div>
        <button
          onClick={handleRunNow}
          disabled={running}
          className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          {running ? 'Backing up…' : 'Back up now'}
        </button>
      </header>

      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-sage/40 text-left text-xs font-medium text-ink-faint">
              <th className="px-4 py-2">Created</th>
              <th className="px-4 py-2">Size</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {backups.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-ink-faint">
                  No backups yet — the first automatic one runs tonight at 2 AM, or tap "Back up now".
                </td>
              </tr>
            )}
            {backups.map((b) => (
              <tr key={b.filename} className="border-b border-line last:border-0">
                <td className="px-4 py-3 text-ink">{formatWhen(b.created_at)}</td>
                <td className="px-4 py-3 text-ink-faint">{formatSize(b.size_bytes)}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => api.downloadBackup(b.filename)}
                    className="text-xs font-medium text-ink-light hover:text-ink"
                  >
                    Download
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
