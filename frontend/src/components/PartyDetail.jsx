import { useEffect, useState } from 'react'
import { api } from '../api'
import { formatINR, formatDate, STATUS_STYLES, resolveImageUrl } from '../utils'
import EditGeneratedBill from './EditGeneratedBill'

export default function PartyDetail({ partyId, onBack }) {
  const [party, setParty] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [editingParty, setEditingParty] = useState(false)
  const [partyForm, setPartyForm] = useState({
    phone: '', gstin: '', address: '', city: '', pincode: '', email: '',
  })

  function reload() {
    api.getParty(partyId).then((p) => {
      setParty(p)
      setPartyForm({
        phone: p.phone || '',
        gstin: p.gstin || '',
        address: p.address || '',
        city: p.city || '',
        pincode: p.pincode || '',
        email: p.email || '',
      })
    })
    api.listInvoices({ party_id: partyId }).then(setInvoices)
  }

  useEffect(() => {
    reload()
  }, [partyId])

  async function savePartyDetails() {
    await api.updateParty(partyId, {
      phone: partyForm.phone || null,
      gstin: partyForm.gstin || null,
      address: partyForm.address || null,
      city: partyForm.city || null,
      pincode: partyForm.pincode || null,
      email: partyForm.email || null,
    })
    setEditingParty(false)
    reload()
  }

  if (!party) return <div className="mx-auto max-w-5xl px-4 py-6 text-sm text-ink-faint">Loading…</div>

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <button onClick={onBack} className="mb-4 text-sm text-ink-faint hover:text-ink">
        ← All parties
      </button>

      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex-1">
          <h1 className="font-display text-2xl font-semibold text-ink">{party.name}</h1>
          {editingParty ? (
            <div className="mt-3 max-w-lg rounded-lg border border-line bg-white p-3">
              <div className="grid grid-cols-2 gap-2">
                <PartyField label="Phone">
                  <input
                    value={partyForm.phone}
                    onChange={(e) => setPartyForm({ ...partyForm, phone: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </PartyField>
                <PartyField label="Email">
                  <input
                    value={partyForm.email}
                    onChange={(e) => setPartyForm({ ...partyForm, email: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </PartyField>
                <PartyField label="GSTIN">
                  <input
                    value={partyForm.gstin}
                    onChange={(e) => setPartyForm({ ...partyForm, gstin: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </PartyField>
                <PartyField label="City">
                  <input
                    value={partyForm.city}
                    onChange={(e) => setPartyForm({ ...partyForm, city: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </PartyField>
                <PartyField label="Pincode">
                  <input
                    value={partyForm.pincode}
                    onChange={(e) => setPartyForm({ ...partyForm, pincode: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </PartyField>
                <PartyField label="Address" className="col-span-2">
                  <input
                    value={partyForm.address}
                    onChange={(e) => setPartyForm({ ...partyForm, address: e.target.value })}
                    className="w-full rounded-md border border-line px-2 py-1.5 text-sm"
                  />
                </PartyField>
              </div>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={savePartyDetails}
                  className="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-paper"
                >
                  Save
                </button>
                <button onClick={() => setEditingParty(false)} className="text-xs text-ink-faint">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-faint">
              {party.phone && <span>{party.phone}</span>}
              {party.email && <span>{party.email}</span>}
              {party.gstin && <span>GSTIN: {party.gstin}</span>}
              {(party.address || party.city || party.pincode) && (
                <span>
                  {[party.address, party.city, party.pincode].filter(Boolean).join(', ')}
                </span>
              )}
              <button onClick={() => setEditingParty(true)} className="text-ink-light hover:text-ink">
                Edit details
              </button>
            </div>
          )}
        </div>
        <div className="flex gap-4 text-sm">
          <MiniStat label="Invoiced" value={party.total_invoiced} />
          <MiniStat label="Received" value={party.total_received} tone="ink-light" />
          <MiniStat label="Outstanding" value={party.outstanding} tone="rust" />
        </div>
      </header>

      <div className="mb-6 flex gap-2">
        <button
          onClick={() => api.downloadPartyPdf(party.id)}
          className="rounded-md border border-ink/30 px-3 py-1.5 text-xs font-medium text-ink hover:bg-sage"
        >
          Export PDF statement
        </button>
        <button
          onClick={() => api.downloadPartyExcel(party.id)}
          className="rounded-md border border-ink/30 px-3 py-1.5 text-xs font-medium text-ink hover:bg-sage"
        >
          Export Excel
        </button>
      </div>

      <div className="space-y-3">
        {invoices.length === 0 && (
          <p className="rounded-lg border border-dashed border-line bg-white p-8 text-center text-sm text-ink-faint">
            No invoices for this party yet.
          </p>
        )}
        {invoices.map((inv) => (
          <InvoiceCard
            key={inv.id}
            invoice={inv}
            expanded={expandedId === inv.id}
            onToggle={() => setExpandedId(expandedId === inv.id ? null : inv.id)}
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

function InvoiceCard({ invoice, expanded, onToggle, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [editingBill, setEditingBill] = useState(false)
  const [form, setForm] = useState({
    invoice_number: invoice.invoice_number || '',
    invoice_date: invoice.invoice_date || '',
    amount: invoice.amount,
    remarks: invoice.remarks || '',
  })
  const [addingPayment, setAddingPayment] = useState(false)

  const s = STATUS_STYLES[invoice.status] || STATUS_STYLES.unpaid

  async function saveEdit() {
    await api.updateInvoice(invoice.id, {
      invoice_number: form.invoice_number || null,
      invoice_date: form.invoice_date || null,
      amount: parseFloat(form.amount),
      remarks: form.remarks || null,
      changed_by: 'user',
    })
    setEditing(false)
    onChanged()
  }

  async function deleteThisInvoice() {
    const paymentWarning = invoice.payments.length > 0
      ? ` This will also delete its ${invoice.payments.length} payment${invoice.payments.length > 1 ? 's' : ''}.`
      : ''
    if (!confirm(`Delete this invoice permanently?${paymentWarning}`)) return
    await api.deleteInvoice(invoice.id)
    onChanged()
  }

  return (
    <div className="torn-edge rounded-lg border border-line bg-white p-4">
      <div className="flex cursor-pointer items-center justify-between" onClick={onToggle}>
        <div className="flex items-center gap-3">
          <span className={`stamp px-2 py-0.5 text-xs font-semibold ${s.className}`}>{s.label}</span>
          <div>
            <p className="text-sm font-medium text-ink">
              {invoice.invoice_number ? `#${invoice.invoice_number}` : 'No invoice number'}
            </p>
            <p className="text-xs text-ink-faint">{formatDate(invoice.invoice_date)}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="tabular-nums text-sm font-medium text-ink">{formatINR(invoice.amount)}</span>
          {invoice.outstanding > 0 && (
            <span className="tabular-nums text-xs text-rust">{formatINR(invoice.outstanding)} due</span>
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-4 space-y-4 border-t border-line pt-4">
          {invoice.raw_image_url && !editingBill && (
            <a
              href={resolveImageUrl(invoice.raw_image_url)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block"
            >
              <img
                src={resolveImageUrl(invoice.raw_image_url)}
                alt="Bill"
                className="h-24 w-24 rounded-md border border-line object-cover hover:opacity-80"
              />
            </a>
          )}

          {editingBill ? (
            <EditGeneratedBill
              invoice={invoice}
              onCancel={() => setEditingBill(false)}
              onSaved={() => {
                setEditingBill(false)
                onChanged()
              }}
            />
          ) : editing ? (
            <div className="grid grid-cols-2 gap-3">
              <LabeledInput
                label="Invoice number"
                value={form.invoice_number}
                onChange={(v) => setForm({ ...form, invoice_number: v })}
              />
              <LabeledInput
                label="Date"
                type="date"
                value={form.invoice_date}
                onChange={(v) => setForm({ ...form, invoice_date: v })}
              />
              <LabeledInput
                label="Amount"
                type="number"
                value={form.amount}
                onChange={(v) => setForm({ ...form, amount: v })}
              />
              <LabeledInput
                label="Remarks"
                value={form.remarks}
                onChange={(v) => setForm({ ...form, remarks: v })}
              />
              <div className="col-span-2 flex gap-2">
                <button
                  onClick={saveEdit}
                  className="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-paper hover:bg-ink-light"
                >
                  Save
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="rounded-md border border-line px-3 py-1.5 text-xs text-ink-faint"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                {invoice.remarks && <p className="text-sm text-ink-faint">Note: {invoice.remarks}</p>}
                {invoice.is_generated && (invoice.shipped_by || invoice.vehicle_number) && (
                  <p className="text-xs text-ink-faint">
                    {[invoice.shipped_by, invoice.vehicle_number, invoice.driver_contact].filter(Boolean).join(' · ')}
                  </p>
                )}
              </div>
              <div className="ml-auto flex gap-3">
                {invoice.is_generated ? (
                  <button
                    onClick={() => setEditingBill(true)}
                    className="text-xs font-medium text-ink-light hover:text-ink"
                  >
                    Edit bill
                  </button>
                ) : (
                  <button
                    onClick={() => setEditing(true)}
                    className="text-xs font-medium text-ink-light hover:text-ink"
                  >
                    Edit invoice
                  </button>
                )}
                <button
                  onClick={deleteThisInvoice}
                  className="text-xs font-medium text-rust hover:underline"
                >
                  Delete invoice
                </button>
              </div>
            </div>
          )}

          <div>
            <p className="mb-2 text-xs font-medium text-ink-faint">Payments</p>
            {invoice.payments.length === 0 && (
              <p className="text-sm text-ink-faint">No payments recorded yet.</p>
            )}
            <ul className="space-y-2">
              {invoice.payments.map((p) => (
                <PaymentRow key={p.id} payment={p} onChanged={onChanged} />
              ))}
            </ul>
          </div>

          {addingPayment ? (
            <AddPaymentForm
              invoiceId={invoice.id}
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

function PaymentRow({ payment, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    amount: payment.amount,
    payment_date: payment.payment_date,
    mode: payment.mode,
    remarks: payment.remarks || '',
  })

  async function save() {
    await api.updatePayment(payment.id, {
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
    await api.deletePayment(payment.id)
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

function AddPaymentForm({ invoiceId, onDone, onCancel }) {
  const [amount, setAmount] = useState('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [mode, setMode] = useState('cash')
  const [remarks, setRemarks] = useState('')

  async function submit() {
    if (!amount) return
    await api.addPayment(invoiceId, { amount: parseFloat(amount), payment_date: date, mode, remarks: remarks || null })
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

function PartyField({ label, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs font-medium text-ink-faint">{label}</span>
      {children}
    </label>
  )
}
