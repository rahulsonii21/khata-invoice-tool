import { useEffect, useState } from 'react'
import { api, fetchFileBlob } from '../api'
import { formatINR, formatDate, getStatusStyle, resolveImageUrl, compressImage } from '../utils'

export default function SupplierDetail({ supplierId, onBack }) {
  const [supplier, setSupplier] = useState(null)
  const [purchases, setPurchases] = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [editingSupplier, setEditingSupplier] = useState(false)
  const [addingPurchase, setAddingPurchase] = useState(false)
  const [monthFilter, setMonthFilter] = useState('')
  const [supplierForm, setSupplierForm] = useState({
    phone: '', gstin: '', address: '', city: '', pincode: '', email: '',
  })

  function reload() {
    api.getSupplier(supplierId).then((s) => {
      setSupplier(s)
      setSupplierForm({
        phone: s.phone || '',
        gstin: s.gstin || '',
        address: s.address || '',
        city: s.city || '',
        pincode: s.pincode || '',
        email: s.email || '',
      })
    })
    const params = { supplier_id: supplierId }
    if (monthFilter) params.month = monthFilter
    api.listPurchases(params).then(setPurchases)
  }

  useEffect(() => {
    reload()
  }, [supplierId, monthFilter])

  async function saveSupplierDetails() {
    await api.updateSupplier(supplierId, {
      phone: supplierForm.phone || null,
      gstin: supplierForm.gstin || null,
      address: supplierForm.address || null,
      city: supplierForm.city || null,
      pincode: supplierForm.pincode || null,
      email: supplierForm.email || null,
    })
    setEditingSupplier(false)
    reload()
  }

  if (!supplier) return <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-ink-faint">Loading…</div>

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <button onClick={onBack} className="mb-4 text-sm text-ink-faint hover:text-ink">
        ← All suppliers
      </button>

      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex-1">
          <h1 className="font-display text-2xl font-semibold text-ink">{supplier.name}</h1>
          {editingSupplier ? (
            <div className="mt-3 max-w-lg rounded-lg border border-line bg-white p-3">
              <div className="grid grid-cols-2 gap-2">
                <Field label="Phone">
                  <input
                    value={supplierForm.phone}
                    onChange={(e) => setSupplierForm({ ...supplierForm, phone: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </Field>
                <Field label="Email">
                  <input
                    value={supplierForm.email}
                    onChange={(e) => setSupplierForm({ ...supplierForm, email: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </Field>
                <Field label="GSTIN">
                  <input
                    value={supplierForm.gstin}
                    onChange={(e) => setSupplierForm({ ...supplierForm, gstin: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </Field>
                <Field label="City">
                  <input
                    value={supplierForm.city}
                    onChange={(e) => setSupplierForm({ ...supplierForm, city: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </Field>
                <Field label="Pincode">
                  <input
                    value={supplierForm.pincode}
                    onChange={(e) => setSupplierForm({ ...supplierForm, pincode: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </Field>
                <Field label="Address" className="col-span-2">
                  <input
                    value={supplierForm.address}
                    onChange={(e) => setSupplierForm({ ...supplierForm, address: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </Field>
              </div>
              <div className="mt-3 flex gap-2">
                <button onClick={saveSupplierDetails} className="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-paper">
                  Save
                </button>
                <button onClick={() => setEditingSupplier(false)} className="text-xs text-ink-faint">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-faint">
              {supplier.phone && <span>{supplier.phone}</span>}
              {supplier.email && <span>{supplier.email}</span>}
              {supplier.gstin && <span>GSTIN: {supplier.gstin}</span>}
              {(supplier.address || supplier.city || supplier.pincode) && (
                <span>{[supplier.address, supplier.city, supplier.pincode].filter(Boolean).join(', ')}</span>
              )}
              <button onClick={() => setEditingSupplier(true)} className="text-ink-light hover:text-ink">
                Edit details
              </button>
            </div>
          )}
        </div>
        <div className="flex gap-4 text-sm">
          <MiniStat label="Purchased" value={supplier.total_purchased} />
          <MiniStat label="Paid" value={supplier.total_paid} tone="ink-light" />
          <MiniStat label="Payable" value={supplier.outstanding} tone="rust" />
        </div>
      </header>

      <div className="mb-4 flex items-center gap-2">
        <button
          onClick={() => setAddingPurchase((s) => !s)}
          className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper hover:bg-ink-light"
        >
          + Add purchase
        </button>
        <label className="ml-auto text-xs font-medium text-ink-faint">Filter by month:</label>
        <input
          type="month"
          value={monthFilter}
          onChange={(e) => setMonthFilter(e.target.value)}
          className="rounded-md border border-line px-2 py-1 text-sm"
        />
        {monthFilter && (
          <button onClick={() => setMonthFilter('')} className="text-xs text-ink-faint hover:text-ink">
            Clear
          </button>
        )}
      </div>

      {addingPurchase && (
        <AddPurchaseForm
          supplierId={supplierId}
          onDone={() => {
            setAddingPurchase(false)
            reload()
          }}
          onCancel={() => setAddingPurchase(false)}
        />
      )}

      <div className="space-y-3">
        {purchases.length === 0 && (
          <p className="rounded-lg border border-dashed border-line bg-white p-8 text-center text-sm text-ink-faint">
            {monthFilter ? 'No purchases from this supplier in that month.' : 'No purchases from this supplier yet.'}
          </p>
        )}
        {purchases.map((purchase) => (
          <PurchaseCard
            key={purchase.id}
            purchase={purchase}
            expanded={expandedId === purchase.id}
            onToggle={() => setExpandedId(expandedId === purchase.id ? null : purchase.id)}
            onChanged={reload}
          />
        ))}
      </div>
    </div>
  )
}

function MiniStat({ label, value, tone = 'ink' }) {
  const toneClass = { ink: 'text-ink', 'ink-light': 'text-ink-light', rust: 'text-rust' }[tone]
  return (
    <div className="text-right">
      <p className="text-xs text-ink-faint">{label}</p>
      <p className={`font-display text-lg font-semibold tabular-nums ${toneClass}`}>{formatINR(value)}</p>
    </div>
  )
}

function AddPurchaseForm({ supplierId, onDone, onCancel }) {
  const [form, setForm] = useState({
    purchase_number: '', purchase_date: '', due_date: '', amount: '', gst_amount: '', remarks: '',
  })
  const [photo, setPhoto] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function handleSave() {
    setError(null)
    if (!form.amount) {
      setError('Amount is required.')
      return
    }
    setSaving(true)
    try {
      let raw_image_url = null
      if (photo) {
        const compressed = await compressImage(photo)
        const uploadResult = await api.uploadImage(compressed)
        raw_image_url = uploadResult.image_url
      }
      await api.createPurchase({
        supplier_id: supplierId,
        purchase_number: form.purchase_number || null,
        purchase_date: form.purchase_date || null,
        due_date: form.due_date || null,
        amount: parseFloat(form.amount),
        gst_amount: form.gst_amount ? parseFloat(form.gst_amount) : null,
        remarks: form.remarks || null,
        raw_image_url,
      })
      onDone()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-4 space-y-3 rounded-lg border border-line bg-white p-4">
      {error && <p className="rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Supplier's bill number">
          <input
            value={form.purchase_number}
            onChange={(e) => setForm({ ...form, purchase_number: e.target.value })}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Purchase date">
          <input
            type="date"
            value={form.purchase_date}
            onChange={(e) => setForm({ ...form, purchase_date: e.target.value })}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Due date (optional)">
          <input
            type="date"
            value={form.due_date}
            onChange={(e) => setForm({ ...form, due_date: e.target.value })}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
        <Field label="Amount">
          <input
            type="number"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm tabular-nums"
          />
        </Field>
        <Field label="GST amount (optional)">
          <input
            type="number"
            value={form.gst_amount}
            onChange={(e) => setForm({ ...form, gst_amount: e.target.value })}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm tabular-nums"
          />
        </Field>
        <Field label="Remarks (optional)">
          <input
            value={form.remarks}
            onChange={(e) => setForm({ ...form, remarks: e.target.value })}
            className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
          />
        </Field>
      </div>
      <label className="block text-xs font-medium text-ink-faint">
        Bill photo (optional)
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => setPhoto(e.target.files[0])}
          className="mt-1 block text-xs"
        />
      </label>
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save purchase'}
        </button>
        <button onClick={onCancel} className="rounded-md border border-line px-4 py-2 text-sm text-ink-faint">
          Cancel
        </button>
      </div>
    </div>
  )
}

function PurchaseCard({ purchase, expanded, onToggle, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    purchase_number: purchase.purchase_number || '',
    purchase_date: purchase.purchase_date || '',
    due_date: purchase.due_date || '',
    amount: purchase.amount,
    remarks: purchase.remarks || '',
  })
  const [addingPayment, setAddingPayment] = useState(false)

  const s = getStatusStyle(purchase)

  async function saveEdit() {
    await api.updatePurchase(purchase.id, {
      purchase_number: form.purchase_number || null,
      purchase_date: form.purchase_date || null,
      due_date: form.due_date || null,
      amount: parseFloat(form.amount),
      remarks: form.remarks || null,
      changed_by: 'user',
    })
    setEditing(false)
    onChanged()
  }

  async function deleteThisPurchase() {
    const paymentWarning = purchase.payments.length > 0
      ? ` This will also delete its ${purchase.payments.length} payment${purchase.payments.length > 1 ? 's' : ''}.`
      : ''
    if (!confirm(`Delete this purchase permanently?${paymentWarning}`)) return
    await api.deletePurchase(purchase.id)
    onChanged()
  }

  return (
    <div className="torn-edge rounded-lg border border-line bg-white p-4">
      <div className="flex cursor-pointer items-center justify-between" onClick={onToggle}>
        <div className="flex items-center gap-3">
          <span className={`stamp px-2 py-0.5 text-xs font-semibold ${s.className}`}>{s.label}</span>
          <div>
            <p className="text-sm font-medium text-ink">
              {purchase.purchase_number ? `#${purchase.purchase_number}` : 'No bill number'}
            </p>
            <p className="text-xs text-ink-faint">
              {formatDate(purchase.purchase_date)}
              {purchase.due_date && ` · due ${formatDate(purchase.due_date)}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="tabular-nums text-sm font-medium text-ink">{formatINR(purchase.amount)}</span>
          {purchase.outstanding > 0 && (
            <span className="tabular-nums text-xs text-rust">{formatINR(purchase.outstanding)} due</span>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-4 space-y-4 border-t border-line pt-4">
          {purchase.raw_image_url && (
            <a href={resolveImageUrl(purchase.raw_image_url)} target="_blank" rel="noopener noreferrer" className="inline-block">
              <img
                src={resolveImageUrl(purchase.raw_image_url)}
                alt="Bill"
                className="h-24 w-24 rounded-md border border-line object-cover hover:opacity-80"
              />
            </a>
          )}

          {editing ? (
            <div className="grid grid-cols-2 gap-3">
              <LabeledInput label="Bill number" value={form.purchase_number} onChange={(v) => setForm({ ...form, purchase_number: v })} />
              <LabeledInput label="Date" type="date" value={form.purchase_date} onChange={(v) => setForm({ ...form, purchase_date: v })} />
              <LabeledInput label="Due date" type="date" value={form.due_date} onChange={(v) => setForm({ ...form, due_date: v })} />
              <LabeledInput label="Amount" type="number" value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />
              <LabeledInput label="Remarks" value={form.remarks} onChange={(v) => setForm({ ...form, remarks: v })} />
              <div className="col-span-2 flex gap-2">
                <button onClick={saveEdit} className="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-paper">
                  Save
                </button>
                <button onClick={() => setEditing(false)} className="rounded-md border border-line px-3 py-1.5 text-xs text-ink-faint">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              {purchase.remarks && <p className="text-sm text-ink-faint">Note: {purchase.remarks}</p>}
              <div className="ml-auto flex gap-3">
                <button onClick={() => setEditing(true)} className="text-xs font-medium text-ink-light hover:text-ink">
                  Edit purchase
                </button>
                <button onClick={deleteThisPurchase} className="text-xs font-medium text-rust hover:underline">
                  Delete purchase
                </button>
              </div>
            </div>
          )}

          <div>
            <p className="mb-2 text-xs font-medium text-ink-faint">Payments</p>
            {purchase.payments.length === 0 && <p className="text-sm text-ink-faint">No payments recorded yet.</p>}
            <ul className="space-y-2">
              {purchase.payments.map((p) => (
                <PurchasePaymentRow key={p.id} payment={p} onChanged={onChanged} />
              ))}
            </ul>
          </div>

          {addingPayment ? (
            <AddPurchasePaymentForm
              purchaseId={purchase.id}
              onDone={() => {
                setAddingPayment(false)
                onChanged()
              }}
              onCancel={() => setAddingPayment(false)}
            />
          ) : (
            <button
              onClick={() => setAddingPayment(true)}
              className="rounded-md border border-ink/30 px-3 py-1.5 text-xs font-medium text-ink hover:bg-sage"
            >
              + Add payment
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function PurchasePaymentRow({ payment, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    amount: payment.amount,
    payment_date: payment.payment_date,
    mode: payment.mode,
    remarks: payment.remarks || '',
  })

  async function save() {
    await api.updatePurchasePayment(payment.id, {
      amount: parseFloat(form.amount),
      payment_date: form.payment_date,
      mode: form.mode,
      remarks: form.remarks || null,
      changed_by: 'user',
    })
    setEditing(false)
    onChanged()
  }

  async function remove() {
    if (!confirm('Delete this payment?')) return
    await api.deletePurchasePayment(payment.id)
    onChanged()
  }

  if (editing) {
    return (
      <li className="rounded-md bg-sage/40 p-2">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <input
            type="number"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            className="rounded border border-line px-2 py-1 text-xs"
          />
          <input
            type="date"
            value={form.payment_date}
            onChange={(e) => setForm({ ...form, payment_date: e.target.value })}
            className="rounded border border-line px-2 py-1 text-xs"
          />
          <select
            value={form.mode}
            onChange={(e) => setForm({ ...form, mode: e.target.value })}
            className="rounded border border-line px-2 py-1 text-xs"
          >
            <option value="cash">Cash</option>
            <option value="upi">UPI</option>
            <option value="bank">Bank</option>
            <option value="cheque">Cheque</option>
            <option value="other">Other</option>
          </select>
          <input
            value={form.remarks}
            onChange={(e) => setForm({ ...form, remarks: e.target.value })}
            placeholder="Remarks"
            className="rounded border border-line px-2 py-1 text-xs"
          />
        </div>
        <div className="mt-2 flex gap-2">
          <button onClick={save} className="rounded bg-ink px-2 py-1 text-xs text-paper">
            Save
          </button>
          <button onClick={() => setEditing(false)} className="text-xs text-ink-faint">
            Cancel
          </button>
        </div>
      </li>
    )
  }

  return (
    <li className="flex items-center justify-between rounded-md bg-sage/30 px-3 py-2 text-sm">
      <div>
        <span className="tabular-nums font-medium text-ink">{formatINR(payment.amount)}</span>
        <span className="ml-2 text-xs text-ink-faint">
          {formatDate(payment.payment_date)} · {payment.mode}
        </span>
        {payment.remarks && <span className="ml-2 text-xs italic text-ink-faint">"{payment.remarks}"</span>}
      </div>
      <div className="flex gap-2">
        <button onClick={() => setEditing(true)} className="text-xs text-ink-light hover:text-ink">
          Edit
        </button>
        <button onClick={remove} className="text-xs text-rust hover:underline">
          Delete
        </button>
      </div>
    </li>
  )
}

function AddPurchasePaymentForm({ purchaseId, onDone, onCancel }) {
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [mode, setMode] = useState('cash')
  const [remarks, setRemarks] = useState('')

  async function submit() {
    if (!amount) return
    await api.addPurchasePayment(purchaseId, { amount: parseFloat(amount), payment_date: date, mode, remarks: remarks || null })
    onDone()
  }

  return (
    <div className="grid grid-cols-2 gap-2 rounded-md border border-line p-3 sm:grid-cols-4">
      <input
        type="number"
        placeholder="Amount"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="rounded border border-line px-2 py-1 text-xs"
      />
      <input
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        className="rounded border border-line px-2 py-1 text-xs"
      />
      <select value={mode} onChange={(e) => setMode(e.target.value)} className="rounded border border-line px-2 py-1 text-xs">
        <option value="cash">Cash</option>
        <option value="upi">UPI</option>
        <option value="bank">Bank</option>
        <option value="cheque">Cheque</option>
        <option value="other">Other</option>
      </select>
      <input
        placeholder="Remarks"
        value={remarks}
        onChange={(e) => setRemarks(e.target.value)}
        className="rounded border border-line px-2 py-1 text-xs"
      />
      <div className="col-span-2 flex gap-2 sm:col-span-4">
        <button onClick={submit} className="rounded bg-ink px-3 py-1.5 text-xs font-medium text-paper">
          Add payment
        </button>
        <button onClick={onCancel} className="text-xs text-ink-faint">
          Cancel
        </button>
      </div>
    </div>
  )
}

function LabeledInput({ label, value, onChange, type = 'text' }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-faint">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
      />
    </label>
  )
}

function Field({ label, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-medium text-ink-faint">{label}</span>
      {children}
    </label>
  )
}
