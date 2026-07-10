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
  const [restoreTarget, setRestoreTarget] = useState(null)

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
                    className="mr-3 text-xs font-medium text-ink-light hover:text-ink"
                  >
                    Download
                  </button>
                  <button
                    onClick={() => setRestoreTarget(b)}
                    className="text-xs font-medium text-rust hover:underline"
                  >
                    Restore
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {restoreTarget && (
        <RestoreConfirmModal
          backup={restoreTarget}
          onClose={() => setRestoreTarget(null)}
          onDone={() => {
            setRestoreTarget(null)
            reload()
          }}
        />
      )}
    </div>
  )
}

function RestoreConfirmModal({ backup, onClose, onDone }) {
  const [confirmText, setConfirmText] = useState('')
  const [restoring, setRestoring] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)

  async function handleRestore() {
    setError(null)
    setRestoring(true)
    try {
      const result = await api.restoreBackup(backup.filename)
      setDone(result.restored)
    } catch (e) {
      setError(e.message)
    } finally {
      setRestoring(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-5">
        {done ? (
          <>
            <h3 className="font-display text-lg font-semibold text-ink">Restore complete</h3>
            <p className="mt-2 text-sm text-ink-faint">
              Replaced with the backup from {formatWhen(backup.created_at)}:
            </p>
            <ul className="mt-2 space-y-1 text-sm text-ink">
              {Object.entries(done).map(([table, count]) => (
                <li key={table}>
                  {count} {table.replace('_', ' ')}
                </li>
              ))}
            </ul>
            <button
              onClick={onDone}
              className="mt-4 w-full rounded-md bg-ink py-2 text-sm font-medium text-paper hover:bg-ink-light"
            >
              Done
            </button>
          </>
        ) : (
          <>
            <h3 className="font-display text-lg font-semibold text-rust">Restore this backup?</h3>
            <p className="mt-2 text-sm text-ink-faint">
              This replaces <span className="font-semibold text-ink">everything currently in the app</span> — every
              party, invoice, payment, supplier, and purchase — with exactly what's in the backup from{' '}
              <span className="font-medium text-ink">{formatWhen(backup.created_at)}</span>. Anything added or
              changed since then will be lost. This cannot be undone, except by restoring a different backup
              afterward.
            </p>
            <p className="mt-3 text-xs font-medium text-ink-faint">
              Type <span className="font-mono text-rust">RESTORE</span> to confirm:
            </p>
            <input
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm"
              placeholder="RESTORE"
            />
            {error && <p className="mt-2 text-sm text-rust">{error}</p>}
            <div className="mt-4 flex gap-2">
              <button
                onClick={handleRestore}
                disabled={confirmText !== 'RESTORE' || restoring}
                className="rounded-md bg-rust px-4 py-2 text-sm font-medium text-paper hover:bg-rust/90 disabled:opacity-40"
              >
                {restoring ? 'Restoring…' : 'Restore and replace everything'}
              </button>
              <button onClick={onClose} className="rounded-md border border-line px-4 py-2 text-sm text-ink-faint">
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
