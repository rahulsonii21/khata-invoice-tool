import { useState, useCallback, useRef, useEffect } from 'react'
import { api } from '../api'
import PartyAutocomplete from './PartyAutocomplete'
import { formatINR, compressImage } from '../utils'

let idCounter = 0
const nextId = () => `b${++idCounter}`

export default function BulkPartyUpload({ direction = 'customer' }) {
  const [parties, setParties] = useState([])
  const [partyName, setPartyName] = useState('')
  const [locked, setLocked] = useState(false) // party chosen, ready to drop files
  const [queue, setQueue] = useState([])
  const [savingAll, setSavingAll] = useState(false)
  const [savedTotal, setSavedTotal] = useState(0)
  const [viewingId, setViewingId] = useState(null)
  const processingRef = useRef(false)

  const isCustomer = direction === 'customer'
  const entityLabel = isCustomer ? 'party' : 'supplier'

  useEffect(() => {
    setLocked(false)
    setQueue([])
    setPartyName('')
    const list = isCustomer ? api.listParties() : api.listSuppliers()
    list.then(setParties).catch(() => {})
  }, [direction])

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

    compressImage(next.file)
      .then((compressed) => api.extractInvoice(compressed))
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
      let entity = parties.find((p) => p.name.toLowerCase() === partyName.toLowerCase())
      if (!entity) {
        entity = isCustomer
          ? await api.createParty({ name: partyName.trim() })
          : await api.createSupplier({ name: partyName.trim() })
        setParties((p) => [...p, entity])
      }

      const toSave = queue.filter((f) => f.status === 'done' && f.fields.amount)
      for (const item of toSave) {
        if (isCustomer) {
          await api.createInvoice({
            party_id: entity.id,
            invoice_number: item.fields.invoice_number || null,
            invoice_date: item.fields.invoice_date || null,
            amount: parseFloat(item.fields.amount),
            gst_amount: item.fields.gst_amount ? parseFloat(item.fields.gst_amount) : null,
            raw_image_url: item.imageUrl,
            ocr_confidence: item.confidence,
          })
        } else {
          await api.createPurchase({
            supplier_id: entity.id,
            purchase_number: item.fields.invoice_number || null,
            purchase_date: item.fields.invoice_date || null,
            amount: parseFloat(item.fields.amount),
            gst_amount: item.fields.gst_amount ? parseFloat(item.fields.gst_amount) : null,
            raw_image_url: item.imageUrl,
            ocr_confidence: item.confidence,
          })
        }
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
          Pick or create the {entityLabel} once - every photo you drop after this gets filed under them.
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
          Change {entityLabel}
        </button>
      </div>

      <Dropzone onFiles={addFiles} entityLabel={entityLabel} />

      {queue.length > 0 && (
        <div className="mt-4 space-y-2">
          {queue.map((item) => (
            <BulkRow
              key={item.id}
              item={item}
              onChange={(field, value) => updateField(item.id, field, value)}
              onRemove={() => removeItem(item.id)}
              onView={() => setViewingId(item.id)}
              entityLabel={entityLabel}
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

      {viewingId && (
        <ImageModal
          queue={queue}
          viewingId={viewingId}
          onClose={() => setViewingId(null)}
          onNavigate={setViewingId}
          onChange={updateField}
          entityLabel={entityLabel}
        />
      )}
    </div>
  )
}

function Dropzone({ onFiles, entityLabel = 'party' }) {
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
      <p className="font-display text-base text-ink">Drop all the bills for this {entityLabel} here</p>
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

function BulkRow({ item, onChange, onRemove, onView, entityLabel = 'party' }) {
  const numberPlaceholder = entityLabel === 'party' ? 'Invoice #' : 'Bill #'
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
      <img
        src={item.previewUrl}
        alt=""
        onClick={onView}
        className="h-14 w-14 flex-shrink-0 cursor-pointer rounded-md border border-line object-cover hover:opacity-80"
      />

      {isProcessing && <span className="text-sm text-ink-faint">Reading…</span>}
      {isError && <span className="text-sm text-rust">Couldn't read: {item.error}</span>}

      {item.status === 'done' || isSaved ? (
        <>
          <input
            placeholder={numberPlaceholder}
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

      {(item.status === 'done' || isSaved) && (
        <button onClick={onView} className="text-xs text-ink-light hover:text-ink">
          View
        </button>
      )}

      {!isSaved && (
        <button onClick={onRemove} className="ml-auto text-xs text-ink-faint hover:text-rust">
          Remove
        </button>
      )}
    </div>
  )
}

function ImageModal({ queue, viewingId, onClose, onNavigate, onChange, entityLabel = 'party' }) {
  const isCustomer = entityLabel === 'party'
  const numberLabel = isCustomer ? 'Invoice number' : "Supplier's bill number"
  const dateLabel = isCustomer ? 'Invoice date' : 'Purchase date'
  const item = queue.find((f) => f.id === viewingId)
  if (!item) return null

  const index = queue.findIndex((f) => f.id === viewingId)
  const prevItem = queue[index - 1]
  const nextItem = queue[index + 1]
  const isSaved = item.status === 'saved'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="grid max-h-[90vh] w-full max-w-3xl grid-cols-1 gap-4 overflow-auto rounded-lg bg-white p-4 sm:grid-cols-2"
      >
        <div>
          <img
            src={item.previewUrl}
            alt="Bill"
            className="w-full rounded-md border border-line object-contain"
          />
          {item.confidence != null && item.confidence < 0.6 && (
            <p className="mt-2 rounded-md bg-marigold/10 px-3 py-2 text-xs text-marigold">
              Low confidence extraction — please double-check the fields.
            </p>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-display text-lg font-semibold text-ink">Bill details</h3>
            <button onClick={onClose} className="text-ink-faint hover:text-ink">
              ✕
            </button>
          </div>

          <ModalField label={numberLabel}>
            <input
              value={item.fields.invoice_number}
              onChange={(e) => onChange(item.id, 'invoice_number', e.target.value)}
              disabled={isSaved}
              className="w-full rounded-md border border-line px-3 py-2 text-sm disabled:bg-sage/20"
            />
          </ModalField>
          <ModalField label={dateLabel}>
            <input
              type="date"
              value={item.fields.invoice_date}
              onChange={(e) => onChange(item.id, 'invoice_date', e.target.value)}
              disabled={isSaved}
              className="w-full rounded-md border border-line px-3 py-2 text-sm disabled:bg-sage/20"
            />
          </ModalField>
          <ModalField label="Amount">
            <input
              type="number"
              value={item.fields.amount}
              onChange={(e) => onChange(item.id, 'amount', e.target.value)}
              disabled={isSaved}
              className="w-full rounded-md border border-line px-3 py-2 text-sm tabular-nums disabled:bg-sage/20"
            />
          </ModalField>
          <ModalField label="GST amount (optional)">
            <input
              type="number"
              value={item.fields.gst_amount}
              onChange={(e) => onChange(item.id, 'gst_amount', e.target.value)}
              disabled={isSaved}
              className="w-full rounded-md border border-line px-3 py-2 text-sm tabular-nums disabled:bg-sage/20"
            />
          </ModalField>

          <div className="flex justify-between pt-2">
            <button
              onClick={() => prevItem && onNavigate(prevItem.id)}
              disabled={!prevItem}
              className="text-sm text-ink-faint hover:text-ink disabled:opacity-30"
            >
              ← Previous
            </button>
            <button
              onClick={() => nextItem && onNavigate(nextItem.id)}
              disabled={!nextItem}
              className="text-sm text-ink-faint hover:text-ink disabled:opacity-30"
            >
              Next →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ModalField({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-faint">{label}</span>
      {children}
    </label>
  )
}
