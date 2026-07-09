import { useState, useCallback, useRef, useEffect } from 'react'
import { api } from '../api'
import PartyAutocomplete from './PartyAutocomplete'
import ManualEntry from './ManualEntry'
import BulkPartyUpload from './BulkPartyUpload'
import { compressImage } from '../utils'

let idCounter = 0
const nextId = () => `f${++idCounter}`

const STATUS_LABEL = {
  pending: 'Waiting',
  processing: 'Reading…',
  done: 'Ready to review',
  error: 'Failed',
  saved: 'Saved',
}

export default function UploadReview() {
  const [mode, setMode] = useState('photo') // 'photo' | 'manual' | 'bulk'
  const [queue, setQueue] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [parties, setParties] = useState([])
  const [savedCount, setSavedCount] = useState(0)
  const processingRef = useRef(false)

  useEffect(() => {
    api.listParties().then(setParties).catch(() => {})
  }, [])

  const addFiles = useCallback((fileList) => {
    const items = Array.from(fileList).map((file) => ({
      id: nextId(),
      file,
      previewUrl: URL.createObjectURL(file),
      status: 'pending',
      result: null,
      error: null,
      edited: null,
    }))
    setQueue((q) => [...q, ...items])
  }, [])

  // Sequential processing, one request at a time, so a big batch doesn't
  // overload the server (Tesseract OCR runs on the same machine as the API).
  useEffect(() => {
    if (processingRef.current) return
    const next = queue.find((f) => f.status === 'pending')
    if (!next) return

    processingRef.current = true
    setQueue((q) => q.map((f) => (f.id === next.id ? { ...f, status: 'processing' } : f)))

    compressImage(next.file)
      .then((compressed) => api.extractInvoice(compressed))
      .then((result) => {
        setQueue((q) =>
          q.map((f) =>
            f.id === next.id
              ? {
                  ...f,
                  status: 'done',
                  result,
                  edited: {
                    party_name: result.party_name || '',
                    invoice_number: result.invoice_number || '',
                    invoice_date: result.invoice_date || '',
                    amount: result.amount ?? '',
                    gst_amount: result.gst_amount ?? '',
                  },
                }
              : f
          )
        )
        setActiveId((cur) => cur || next.id)
      })
      .catch((err) => {
        setQueue((q) =>
          q.map((f) => (f.id === next.id ? { ...f, status: 'error', error: err.message } : f))
        )
      })
      .finally(() => {
        processingRef.current = false
        setTimeout(() => setQueue((q) => [...q]), 600) // small gap before picking up next item
      })
  }, [queue])

  const active = queue.find((f) => f.id === activeId)

  async function handleSave(item) {
    const e = item.edited
    if (!e.party_name || !e.amount) {
      alert('Party name and amount are required.')
      return
    }

    let party = parties.find((p) => p.name.toLowerCase() === e.party_name.toLowerCase())
    if (!party) {
      party = await api.createParty({ name: e.party_name })
      setParties((p) => [...p, party])
    }

    await api.createInvoice({
      party_id: party.id,
      invoice_number: e.invoice_number || null,
      invoice_date: e.invoice_date || null,
      amount: parseFloat(e.amount),
      gst_amount: e.gst_amount ? parseFloat(e.gst_amount) : null,
      raw_image_url: item.result?.image_url ?? null,
      ocr_confidence: item.result?.confidence ?? null,
    })

    setQueue((q) => q.map((f) => (f.id === item.id ? { ...f, status: 'saved' } : f)))

    const nextPending = queue.find((f) => f.status === 'done' && f.id !== item.id)
    setActiveId(nextPending ? nextPending.id : null)
  }

  function updateField(field, value) {
    setQueue((q) =>
      q.map((f) => (f.id === activeId ? { ...f, edited: { ...f.edited, [field]: value } } : f))
    )
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Upload Invoices</h1>
        <p className="mt-1 text-sm text-ink-faint">
          {mode === 'photo'
            ? "Drop invoice photos or scans below. Each is read automatically, then you confirm before it's saved."
            : mode === 'bulk'
            ? 'Pick one party, then drop all their bills at once - review and save them together.'
            : 'Enter invoice details directly - useful when a photo is unclear or unavailable.'}
        </p>
      </header>

      <div className="mb-6 inline-flex rounded-md border border-line bg-white p-1">
        <button
          onClick={() => setMode('photo')}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            mode === 'photo' ? 'bg-ink text-paper' : 'text-ink-faint'
          }`}
        >
          Upload photo
        </button>
        <button
          onClick={() => setMode('bulk')}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            mode === 'bulk' ? 'bg-ink text-paper' : 'text-ink-faint'
          }`}
        >
          Bulk for one party
        </button>
        <button
          onClick={() => setMode('manual')}
          className={`rounded px-3 py-1.5 text-sm font-medium ${
            mode === 'manual' ? 'bg-ink text-paper' : 'text-ink-faint'
          }`}
        >
          Enter manually
        </button>
      </div>

      {mode === 'bulk' && <BulkPartyUpload />}

      {mode === 'manual' && (
        <div>
          <ManualEntry onSaved={() => setSavedCount((c) => c + 1)} />
          {savedCount > 0 && (
            <p className="mt-3 text-center text-sm text-ink-light">
              {savedCount} invoice{savedCount > 1 ? 's' : ''} saved this session.
            </p>
          )}
        </div>
      )}

      {mode === 'photo' && (
        <>
          <Dropzone onFiles={addFiles} />

          {queue.length > 0 && (
            <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-[280px_1fr]">
              <QueueList queue={queue} activeId={activeId} onSelect={setActiveId} />
              {active ? (
                <ReviewPanel
                  key={active.id}
                  item={active}
                  parties={parties}
                  onChange={updateField}
                  onSave={() => handleSave(active)}
                />
              ) : (
                <div className="flex items-center justify-center rounded-lg border border-dashed border-line bg-white/50 p-12 text-sm text-ink-faint">
                  {queue.every((f) => f.status === 'saved')
                    ? 'All invoices saved.'
                    : 'Waiting for extraction to finish…'}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Dropzone({ onFiles }) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragOver(false)
        onFiles(e.dataTransfer.files)
      }}
      onClick={() => inputRef.current?.click()}
      className={`torn-edge cursor-pointer rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
        dragOver ? 'border-ink bg-sage' : 'border-line bg-white'
      }`}
    >
      <p className="font-display text-lg text-ink">Tap to upload or drag files here</p>
      <p className="mt-1 text-sm text-ink-faint">JPG, PNG — camera photos work fine</p>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="hidden"
        onChange={(e) => e.target.files.length && onFiles(e.target.files)}
      />
    </div>
  )
}

function QueueList({ queue, activeId, onSelect }) {
  return (
    <ul className="space-y-2">
      {queue.map((f) => (
        <li
          key={f.id}
          onClick={() => f.status !== 'saved' && onSelect(f.id)}
          className={`flex cursor-pointer items-center gap-3 rounded-md border p-2 text-sm ${
            f.id === activeId ? 'border-ink bg-sage' : 'border-line bg-white'
          } ${f.status === 'saved' ? 'opacity-50' : ''}`}
        >
          <img src={f.previewUrl} alt="" className="h-10 w-10 rounded object-cover" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-ink">{f.file.name}</p>
            <p
              className={`text-xs ${
                f.status === 'error'
                  ? 'text-rust'
                  : f.status === 'saved'
                  ? 'text-ink-light'
                  : 'text-marigold'
              }`}
            >
              {STATUS_LABEL[f.status]}
            </p>
          </div>
        </li>
      ))}
    </ul>
  )
}

function ReviewPanel({ item, parties, onChange, onSave }) {
  if (item.status === 'error') {
    return (
      <div className="rounded-lg border border-rust/40 bg-white p-6">
        <p className="font-medium text-rust">Couldn't read this invoice</p>
        <p className="mt-1 text-sm text-ink-faint">{item.error}</p>
      </div>
    )
  }

  if (item.status !== 'done') {
    return (
      <div className="flex items-center justify-center rounded-lg border border-line bg-white p-12 text-sm text-ink-faint">
        Reading invoice…
      </div>
    )
  }

  const e = item.edited
  const confidence = item.result?.confidence
  const lowConfidence = confidence != null && confidence < 0.6

  return (
    <div className="grid grid-cols-1 gap-4 rounded-lg border border-line bg-white p-4 sm:grid-cols-2">
      <div>
        <img src={item.previewUrl} alt="Invoice" className="w-full rounded-md border border-line" />
        {lowConfidence && (
          <p className="mt-2 rounded-md bg-marigold/10 px-3 py-2 text-xs text-marigold">
            Low confidence extraction — please double-check the fields.
          </p>
        )}
      </div>

      <div className="space-y-3">
        <Field label="Party">
          <PartyAutocomplete
            value={e.party_name}
            onChange={(v) => onChange('party_name', v)}
            parties={parties}
          />
        </Field>
        <Field label="Invoice number">
          <input
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
            value={e.invoice_number}
            onChange={(ev) => onChange('invoice_number', ev.target.value)}
          />
        </Field>
        <Field label="Invoice date">
          <input
            type="date"
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
            value={e.invoice_date}
            onChange={(ev) => onChange('invoice_date', ev.target.value)}
          />
        </Field>
        <Field label="Amount">
          <input
            type="number"
            step="0.01"
            className="w-full rounded-md border border-line px-3 py-2 text-sm tabular-nums"
            value={e.amount}
            onChange={(ev) => onChange('amount', ev.target.value)}
          />
        </Field>
        <Field label="GST amount (optional)">
          <input
            type="number"
            step="0.01"
            className="w-full rounded-md border border-line px-3 py-2 text-sm tabular-nums"
            value={e.gst_amount}
            onChange={(ev) => onChange('gst_amount', ev.target.value)}
          />
        </Field>

        <button
          onClick={onSave}
          className="mt-2 w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light"
        >
          Save & next
        </button>
      </div>
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
