import { useState } from 'react'
import { api } from '../api'
import { resolveImageUrl } from '../utils'

let rowId = 0
const nextRowId = () => `erow${++rowId}`

export default function EditGeneratedBill({ invoice, onSaved, onCancel }) {
  const storedItems = (() => {
    try {
      const parsed = JSON.parse(invoice.items_json || '[]')
      return parsed.length > 0 ? parsed : [{ description: '', qty_label: '', rate: '', amount: '', hsn_code: '' }]
    } catch {
      return [{ description: '', qty_label: '', rate: '', amount: '', hsn_code: '' }]
    }
  })()

  const [billNumber, setBillNumber] = useState(invoice.invoice_number || '')
  const [billDate, setBillDate] = useState(invoice.invoice_date || '')
  const [dueDate, setDueDate] = useState(invoice.due_date || '')
  const [items, setItems] = useState(storedItems.map((r) => ({ id: nextRowId(), ...r })))
  const [cgstPct, setCgstPct] = useState(invoice.cgst_pct ?? '')
  const [sgstPct, setSgstPct] = useState(invoice.sgst_pct ?? '')
  const [igstPct, setIgstPct] = useState(invoice.igst_pct ?? '')
  const [shippedBy, setShippedBy] = useState(invoice.shipped_by || '')
  const [vehicleNumber, setVehicleNumber] = useState(invoice.vehicle_number || '')
  const [driverContact, setDriverContact] = useState(invoice.driver_contact || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  function updateItem(id, field, value) {
    setItems((rows) => rows.map((r) => (r.id === id ? { ...r, [field]: value } : r)))
  }

  function addRow() {
    setItems((rows) => [...rows, { id: nextRowId(), description: '', qty_label: '', rate: '', amount: '', hsn_code: '' }])
  }

  function removeRow(id) {
    setItems((rows) => (rows.length > 1 ? rows.filter((r) => r.id !== id) : rows))
  }

  const subtotal = items.reduce((sum, r) => sum + (parseFloat(r.amount) || 0), 0)
  const gstTotal = subtotal * ((parseFloat(cgstPct) || 0) + (parseFloat(sgstPct) || 0) + (parseFloat(igstPct) || 0)) / 100
  const grandTotal = subtotal + gstTotal

  async function handleSave() {
    setError(null)
    const validItems = items.filter((r) => r.description.trim() && r.amount)
    if (validItems.length === 0) {
      setError('At least one item with a description and amount is required.')
      return
    }
    setSaving(true)
    try {
      const result = await api.regenerateBill(invoice.id, {
        bill_number: billNumber || null,
        bill_date: billDate || null,
        due_date: dueDate || null,
        items: validItems.map((r) => ({
          description: r.description,
          qty_label: r.qty_label,
          rate: r.rate ? parseFloat(r.rate) : null,
          amount: parseFloat(r.amount),
          hsn_code: r.hsn_code || null,
        })),
        cgst_pct: parseFloat(cgstPct) || 0,
        sgst_pct: parseFloat(sgstPct) || 0,
        igst_pct: parseFloat(igstPct) || 0,
        shipped_by: shippedBy || null,
        vehicle_number: vehicleNumber || null,
        driver_contact: driverContact || null,
      })
      onSaved(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-line bg-sage/20 p-4">
      {error && <p className="rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}

      <div className="grid grid-cols-3 gap-3">
        <Field label="Bill number">
          <input
            value={billNumber}
            onChange={(e) => setBillNumber(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Date">
          <input
            type="date"
            value={billDate}
            onChange={(e) => setBillDate(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Due date">
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
      </div>

      <div>
        <p className="mb-2 text-xs font-medium text-ink-faint">Items</p>
        <div className="space-y-2">
          {items.map((row) => (
            <div key={row.id} className="rounded-md border border-line p-2">
              <div className="grid grid-cols-12 gap-2">
                <input
                  placeholder="Description"
                  value={row.description}
                  onChange={(e) => updateItem(row.id, 'description', e.target.value)}
                  className="col-span-6 rounded-md border border-line px-2 py-1.5 text-sm"
                />
                <input
                  placeholder="Qty"
                  value={row.qty_label}
                  onChange={(e) => updateItem(row.id, 'qty_label', e.target.value)}
                  className="col-span-3 rounded-md border border-line px-2 py-1.5 text-sm"
                />
                <input
                  type="number"
                  placeholder="Rate"
                  value={row.rate}
                  onChange={(e) => updateItem(row.id, 'rate', e.target.value)}
                  className="col-span-2 rounded-md border border-line px-2 py-1.5 text-sm tabular-nums"
                />
                <button onClick={() => removeRow(row.id)} className="col-span-1 text-xs text-ink-faint hover:text-rust">
                  ✕
                </button>
              </div>
              <div className="mt-2 grid grid-cols-12 gap-2">
                <input
                  placeholder="HSN/SAC code (optional)"
                  value={row.hsn_code || ''}
                  onChange={(e) => updateItem(row.id, 'hsn_code', e.target.value)}
                  className="col-span-6 rounded-md border border-line px-2 py-1.5 text-xs"
                />
                <input
                  type="number"
                  placeholder="Amount"
                  value={row.amount}
                  onChange={(e) => updateItem(row.id, 'amount', e.target.value)}
                  className="col-span-6 rounded-md border border-line px-2 py-1.5 text-sm tabular-nums"
                />
              </div>
            </div>
          ))}
        </div>
        <button onClick={addRow} className="mt-2 text-xs font-medium text-ink-light hover:text-ink">
          + Add item
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Field label="Shipped by">
          <input
            value={shippedBy}
            onChange={(e) => setShippedBy(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Vehicle number">
          <input
            value={vehicleNumber}
            onChange={(e) => setVehicleNumber(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Driver contact">
          <input
            value={driverContact}
            onChange={(e) => setDriverContact(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Field label="CGST %">
          <input
            type="number"
            value={cgstPct}
            onChange={(e) => setCgstPct(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="SGST %">
          <input
            type="number"
            value={sgstPct}
            onChange={(e) => setSgstPct(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="IGST %">
          <input
            type="number"
            value={igstPct}
            onChange={(e) => setIgstPct(e.target.value)}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-ink-faint">Grand total</span>
        <span className="font-display text-lg font-semibold tabular-nums text-ink">
          ₹{grandTotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </span>
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          {saving ? 'Regenerating…' : 'Save & regenerate bill'}
        </button>
        <button onClick={onCancel} className="rounded-md border border-line px-4 py-2 text-sm text-ink-faint">
          Cancel
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
