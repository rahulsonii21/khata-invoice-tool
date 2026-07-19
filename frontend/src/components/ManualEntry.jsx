import { useState, useEffect } from 'react'
import { api } from '../api'
import PartyAutocomplete from './PartyAutocomplete'
import { compressImage } from '../utils'
import StockItemsPicker, { stockItemsForPayload } from './StockItemsPicker'

export default function ManualEntry({ direction = 'customer', onSaved }) {
  const [entities, setEntities] = useState([])
  const [form, setForm] = useState({
    party_name: '',
    invoice_number: '',
    invoice_date: '',
    due_date: '',
    amount: '',
    gst_amount: '',
    remarks: '',
  })
  const [photo, setPhoto] = useState(null)
  const [photoPreview, setPhotoPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [stockItems, setStockItems] = useState([])

  const isCustomer = direction === 'customer'
  const entityLabel = isCustomer ? 'Party' : 'Supplier'
  const numberLabel = isCustomer ? 'Invoice number' : "Supplier's bill number"
  const dateLabel = isCustomer ? 'Invoice date' : 'Purchase date'
  const recordLabel = isCustomer ? 'invoice' : 'purchase'

  useEffect(() => {
    setForm({
      party_name: '', invoice_number: '', invoice_date: '', due_date: '',
      amount: '', gst_amount: '', remarks: '',
    })
    setPhoto(null)
    setPhotoPreview(null)
    setError(null)
    const list = isCustomer ? api.listParties() : api.listSuppliers()
    list.then(setEntities).catch(() => {})
  }, [direction])

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function handlePhotoSelect(file) {
    if (!file) return
    setPhoto(file)
    setPhotoPreview(URL.createObjectURL(file))
  }

  async function handleSave() {
    setError(null)
    if (!form.party_name || !form.amount) {
      setError(`${entityLabel} name and amount are required.`)
      return
    }
    setSaving(true)
    try {
      let entity = entities.find((x) => x.name.toLowerCase() === form.party_name.toLowerCase())
      if (!entity) {
        entity = isCustomer
          ? await api.createParty({ name: form.party_name })
          : await api.createSupplier({ name: form.party_name })
        setEntities((list) => [...list, entity])
      }

      let image_url = null
      if (photo) {
        const compressed = await compressImage(photo)
        const uploadResult = await api.uploadImage(compressed)
        image_url = uploadResult.image_url
      }

      if (isCustomer) {
        await api.createInvoice({
          party_id: entity.id,
          invoice_number: form.invoice_number || null,
          invoice_date: form.invoice_date || null,
          due_date: form.due_date || null,
          amount: parseFloat(form.amount),
          gst_amount: form.gst_amount ? parseFloat(form.gst_amount) : null,
          remarks: form.remarks || null,
          raw_image_url: image_url,
          ocr_confidence: null,
          stock_items: stockItemsForPayload(stockItems),
        })
      } else {
        await api.createPurchase({
          supplier_id: entity.id,
          purchase_number: form.invoice_number || null,
          purchase_date: form.invoice_date || null,
          due_date: form.due_date || null,
          amount: parseFloat(form.amount),
          gst_amount: form.gst_amount ? parseFloat(form.gst_amount) : null,
          remarks: form.remarks || null,
          raw_image_url: image_url,
          ocr_confidence: null,
        })
      }

      setForm({
        party_name: '', invoice_number: '', invoice_date: '', due_date: '',
        amount: '', gst_amount: '', remarks: '',
      })
      setPhoto(null)
      setPhotoPreview(null)
      setStockItems([])
      onSaved?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl rounded-lg border border-line bg-white p-4">
      <h2 className="mb-4 font-display text-lg font-semibold text-ink">Add {recordLabel} manually</h2>

      {error && <p className="mb-3 rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}

      <div className="space-y-3">
        <Field label={entityLabel}>
          <PartyAutocomplete
            value={form.party_name}
            onChange={(v) => update('party_name', v)}
            parties={entities}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label={numberLabel}>
            <input
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
              value={form.invoice_number}
              onChange={(e) => update('invoice_number', e.target.value)}
            />
          </Field>
          <Field label={dateLabel}>
            <input
              type="date"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
              value={form.invoice_date}
              onChange={(e) => update('invoice_date', e.target.value)}
            />
          </Field>
          <Field label="Due date (optional)">
            <input
              type="date"
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
              value={form.due_date}
              onChange={(e) => update('due_date', e.target.value)}
            />
          </Field>
          <Field label="Amount">
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-line px-3 py-2 text-sm tabular-nums"
              value={form.amount}
              onChange={(e) => update('amount', e.target.value)}
            />
          </Field>
          <Field label="GST amount (optional)">
            <input
              type="number"
              step="0.01"
              className="w-full rounded-md border border-line px-3 py-2 text-sm tabular-nums"
              value={form.gst_amount}
              onChange={(e) => update('gst_amount', e.target.value)}
            />
          </Field>
        </div>

        <Field label="Remarks (optional)">
          <input
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
            value={form.remarks}
            onChange={(e) => update('remarks', e.target.value)}
          />
        </Field>

        <Field label="Bill photo (optional)">
          {photoPreview ? (
            <div className="flex items-center gap-3">
              <img src={photoPreview} alt="Bill preview" className="h-16 w-16 rounded-md border border-line object-cover" />
              <button
                onClick={() => {
                  setPhoto(null)
                  setPhotoPreview(null)
                }}
                className="text-xs text-rust hover:underline"
              >
                Remove
              </button>
            </div>
          ) : (
            <label className="flex w-full cursor-pointer items-center justify-center rounded-md border border-dashed border-line py-3 text-sm text-ink-faint hover:bg-sage/30">
              Tap to attach a photo of the bill
              <input
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(e) => handlePhotoSelect(e.target.files[0])}
              />
            </label>
          )}
        </Field>

        {isCustomer && <StockItemsPicker value={stockItems} onChange={setStockItems} />}

        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          {saving ? 'Saving…' : `Save ${recordLabel}`}
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
