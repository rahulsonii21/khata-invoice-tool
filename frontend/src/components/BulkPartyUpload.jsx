import { useState, useCallback, useRef, useEffect } from 'react'
import { api } from '../api'
import PartyAutocomplete from './PartyAutocomplete'
import { formatINR } from '../utils'

let idCounter = 0
const nextId = () => `b${++idCounter}`

export default function BulkPartyUpload() {
  const [parties, setParties] = useState([])
  const [partyName, setPartyName] = useState('')
  const [locked, setLocked] = useState(false) // party chosen, ready to drop files
  const [queue, setQueue] = useState([])
  const [savingAll, setSavingAll] = useState(false)
  const [savedTotal, setSavedTotal] = useState(0)
  const processingRef = useRef(false)

  useEffect(() => {
    api.listParties().then(setParties).catch(() => {})
  }, [])

  const addFiles = useCallback((fileList) => {
    const items = Array.from(fileList).map((file) => ({
      id: nextId(),
      file,
      previewUrl: URL.createObjectURL(file),
      status: 'pending', // pending -> processing -> done -> saved / error
      fields: { invoice_number: '', invoice_date: '', amount: '', gst_amount: '' },
      confidence: null,
      imageUrl: null,
      error: null,
    }))
    setQueue((q) => [...q, ...items])
  }, [])

  // Process one file at a time so a big batch doesn't hammer the server
  useEffect(() => {
    if (processingRef.current) return
    const next = queue.find((f) => f.status === 'pending')
    if (!next) return

    processingRef.current = true
    setQueue((q) => q.map((f) => (f.id === next.id ? { ...f, status: 'processing' } : f)))

    api
      .extractInvoice(next.file)
      .then((result) => {
        setQueue((q) =>
          q.map((f) =>
            f.id === next.id
              ? {
                  ...f,
                  status: 'done',
                  confidence: result.confidence,
                  imageUrl: result.image_url,
                  fields: {
                    invoice_number: result.invoice_number || '',
                    invoice_date: result.invoice_date || '',
                    amount: result.amount ?? '',
                    gst_amount: result.gst_amount ?? '',
                  },
                }
              : f
          )
        )
      })
      .catch((err) => {
        setQueue((q) => (q.map((f) => (f.id === next.id ? { ...f, status: 'error', error: err.message } : f))))
      })
      .finally(() => {
        processingRef.current = false
        setTimeout(() => setQueue((q) => [...q]), 300)
      })
  }, [queue])

  function updateField(id, field, value) {
    setQueue((q) => q.map((f) => (f.id === id ? { ...f, fields: { ...f.fields, [field]: value } } : f)))
  }

  function removeItem(id) {
    setQueue((q) => q.filter((f) => f.id !== id))
  }

  async function handleSaveAll() {
    if (!partyName.trim()) return
    setSavingAll(true)
    try {
      let party = parties.find((p) => p.name.toLowerCase() === partyName.toLowerCase())
      if (!party) {
        party = await api.createParty({ name: partyName.trim() })
        setParties((p) => [...p, party])
      }

      const toSave = queue.filter((f) => f.status === 'done' && f.fields.amount)
      for (const item of toSave) {
        await api.createInvoice({
          party_id: party.id,
          invoice_number: item.fields.invoice_number || null,
          invoice_date: item.fields.invoice_date || null,
          amount: parseFloat(item.fields.amount),
          gst_amount: item.fields.gst_amount ? parseFloat(item.fields.gst_amount) : null,
          raw_image_url: item.imageUrl,
          ocr_confidence: item.confidence,
        })
        setQueue((q) => q.map((f) => (f.id === item.id ? { ...f, status: 'saved' } : f)))
        setSavedTotal((c) => c + 1)
      }
    } finally {
      setSavingAll(false)
    }
  }

  const readyToSaveCount = queue.filter((f) => f.status === 'done' && f.fields.amount).length
  const missingAmountCount = queue.filter((f) => f.status === 'done' && !f.fields.amount).length

  if (!locked) {
    return (
      <div className="mx-auto max-w-md rounded-lg border border-line bg-white p-6">
        <h2 className="mb-1 font-display text-lg font-semibold text-ink">Whose bills are these?</h2>
        <p className="mb-4 text-sm text-ink-faint">
          Pick or create the party once - every photo you drop after this gets filed under them.
        </p>
        <PartyAutocomplete value={partyName} onChange={setPartyName} parties={parties} />
        <button
          onClick={() => partyName.trim() && setLocked(true)}
          disabled={!partyName.trim()}
          className="mt-4 w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          Continue
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between rounded-lg border border-line bg-white px-4 py-3">
        <div>
          <span className="text-xs text-ink-faint">Uploading for</span>
          <p className="font-display text-lg font-semibold text-ink">{partyName}</p>
        </div>
        <button
          onClick={() => {
            setLocked(false)
            setQueue([])
            setPartyName('')
          }}
          className="text-xs text-ink-faint hover:text-ink"
        >
          Change party
        </button>
      </div>

      <Dropzone onFiles={addFiles} />

      {queue.length > 0 && (
        <div className="mt-4 space-y-2">
          {queue.map((item) => (
            <BulkRow
              key={item.id}
              item={item}
              onChange={(field, value) => updateField(item.id, field, value)}
              onRemove={() => removeItem(item.id)}
            />
          ))}

          <div className="sticky bottom-0 mt-4 flex items-center justify-between rounded-lg border border-line bg-white p-3 shadow-md">
            <div className="text-sm text-ink-faint">
              {readyToSaveCount} ready to save
              {missingAmountCount > 0 && `, ${missingAmountCount} need an amount first`}
              {savedTotal > 0 && ` · ${savedTotal} saved this session`}
            </div>
            <button
              onClick={handleSaveAll}
              disabled={savingAll || readyToSaveCount === 0}
              className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
            >
              {savingAll ? 'Saving…' : `Save all (${readyToSaveCount})`}
            </button>
          </div>
        </div>
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
      className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
        dragOver ? 'border-ink bg-sage' : 'border-line bg-white'
      }`}
    >
      <p className="font-display text-base text-ink">Drop all the bills for this party here</p>
      <p className="mt-1 text-sm text-ink-faint">Select multiple files at once - each is read automatically</p>
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

function BulkRow({ item, onChange, onRemove }) {
  const isSaved = item.status === 'saved'
  const isError = item.status === 'error'
  const isProcessing = item.status === 'pending' || item.status === 'processing'
  const lowConfidence = item.confidence != null && item.confidence < 0.6

  return (
    <div
      className={`flex flex-wrap items-center gap-3 rounded-lg border p-3 ${
        isSaved ? 'border-line bg-sage/30 opacity-60' : 'border-line bg-white'
      }`}
    >
      <img src={item.previewUrl} alt="" className="h-14 w-14 flex-shrink-0 rounded-md border border-line object-cover" />

      {isProcessing && <span className="text-sm text-ink-faint">Reading…</span>}
      {isError && <span className="text-sm text-rust">Couldn't read: {item.error}</span>}

      {item.status === 'done' || isSaved ? (
        <>
          <input
            placeholder="Invoice #"
            value={item.fields.invoice_number}
            onChange={(e) => onChange('invoice_number', e.target.value)}
            disabled={isSaved}
            className="w-24 rounded-md border border-line px-2 py-1.5 text-sm disabled:bg-transparent"
          />
          <input
            type="date"
            value={item.fields.invoice_date}
            onChange={(e) => onChange('invoice_date', e.target.value)}
            disabled={isSaved}
            className="rounded-md border border-line px-2 py-1.5 text-sm disabled:bg-transparent"
          />
          <input
            type="number"
            placeholder="Amount"
            value={item.fields.amount}
            onChange={(e) => onChange('amount', e.target.value)}
            disabled={isSaved}
            className={`w-28 rounded-md border px-2 py-1.5 text-sm tabular-nums disabled:bg-transparent ${
              !item.fields.amount ? 'border-rust' : 'border-line'
            }`}
          />
          {lowConfidence && !isSaved && (
            <span className="text-xs text-marigold">low confidence - check fields</span>
          )}
          {isSaved && <span className="text-xs font-medium text-ink-light">Saved ✓</span>}
        </>
      ) : null}

      {!isSaved && (
        <button onClick={onRemove} className="ml-auto text-xs text-ink-faint hover:text-rust">
          Remove
        </button>
      )}
    </div>
  )
}
