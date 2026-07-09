import { useState, useEffect } from 'react'
import { api } from '../api'
import PartyAutocomplete from './PartyAutocomplete'
import { resolveImageUrl } from '../utils'

let rowId = 0
const nextRowId = () => `row${++rowId}`

export default function GenerateBill() {
  const [parties, setParties] = useState([])
  const [partyName, setPartyName] = useState('')
  const [billNumber, setBillNumber] = useState('')
  const [billDate, setBillDate] = useState(new Date().toISOString().slice(0, 10))
  const [items, setItems] = useState([{ id: nextRowId(), description: '', qty_label: '', rate: '', amount: '' }])
  const [cgstPct, setCgstPct] = useState('')
  const [sgstPct, setSgstPct] = useState('')
  const [igstPct, setIgstPct] = useState('')
  const [shippedBy, setShippedBy] = useState('')
  const [vehicleNumber, setVehicleNumber] = useState('')
  const [driverContact, setDriverContact] = useState('')
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => {
    api.listParties().then(setParties).catch(() => {})
  }, [])

  function updateItem(id, field, value) {
    setItems((rows) => rows.map((r) => (r.id === id ? { ...r, [field]: value } : r)))
  }

  function addRow() {
    setItems((rows) => [...rows, { id: nextRowId(), description: '', qty_label: '', rate: '', amount: '' }])
  }

  function removeRow(id) {
    setItems((rows) => (rows.length > 1 ? rows.filter((r) => r.id !== id) : rows))
  }

  const subtotal = items.reduce((sum, r) => sum + (parseFloat(r.amount) || 0), 0)
  const gstTotal = subtotal * ((parseFloat(cgstPct) || 0) + (parseFloat(sgstPct) || 0) + (parseFloat(igstPct) || 0)) / 100
  const grandTotal = subtotal + gstTotal

  async function handleGenerate() {
    setError(null)
    if (!partyName.trim()) {
      setError('Party name is required.')
      return
    }
    const validItems = items.filter((r) => r.description.trim() && r.amount)
    if (validItems.length === 0) {
      setError('At least one item with a description and amount is required.')
      return
    }

    setGenerating(true)
    try {
      let party = parties.find((p) => p.name.toLowerCase() === partyName.toLowerCase())
      if (!party) {
        party = await api.createParty({ name: partyName.trim() })
        setParties((p) => [...p, party])
      }

      const res = await api.generateBill({
        party_id: party.id,
        bill_number: billNumber || null,
        bill_date: billDate || null,
        items: validItems.map((r) => ({
          description: r.description,
          qty_label: r.qty_label,
          rate: r.rate ? parseFloat(r.rate) : null,
          amount: parseFloat(r.amount),
        })),
        cgst_pct: parseFloat(cgstPct) || 0,
        sgst_pct: parseFloat(sgstPct) || 0,
        igst_pct: parseFloat(igstPct) || 0,
        shipped_by: shippedBy || null,
        vehicle_number: vehicleNumber || null,
        driver_contact: driverContact || null,
      })
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  function startNewBill() {
    setResult(null)
    setBillNumber('')
    setItems([{ id: nextRowId(), description: '', qty_label: '', rate: '', amount: '' }])
    setCgstPct('')
    setSgstPct('')
    setIgstPct('')
    setShippedBy('')
    setVehicleNumber('')
    setDriverContact('')
  }

  if (result) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-6">
        <header className="mb-6">
          <h1 className="font-display text-2xl font-semibold text-ink">Bill generated</h1>
          <p className="mt-1 text-sm text-ink-faint">
            Saved to {partyName}'s ledger as an invoice of ₹{result.amount.toLocaleString('en-IN')}.
          </p>
        </header>

        <img
          src={resolveImageUrl(result.image_url)}
          alt="Generated bill"
          className="w-full rounded-lg border border-line"
        />

        <div className="mt-4 flex gap-2">
          <a
            href={resolveImageUrl(result.image_url)}
            download
            className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light"
          >
            Download JPG
          </a>
          <button
            onClick={startNewBill}
            className="rounded-md border border-line px-4 py-2 text-sm text-ink-faint hover:bg-sage/30"
          >
            Create another bill
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Generate Bill</h1>
        <p className="mt-1 text-sm text-ink-faint">
          Creates a bill image using your business letterhead, and saves it to the party's ledger.
        </p>
      </header>

      {error && <p className="mb-4 rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}

      <div className="space-y-4 rounded-lg border border-line bg-white p-4">
        <Field label="Party">
          <PartyAutocomplete value={partyName} onChange={setPartyName} parties={parties} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Bill number">
            <input
              value={billNumber}
              onChange={(e) => setBillNumber(e.target.value)}
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
          </Field>
          <Field label="Date">
            <input
              type="date"
              value={billDate}
              onChange={(e) => setBillDate(e.target.value)}
              className="w-full rounded-md border border-line px-3 py-2 text-sm"
            />
          </Field>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium text-ink-faint">Items</p>
          <div className="space-y-2">
            {items.map((row) => (
              <div key={row.id} className="grid grid-cols-12 gap-2">
                <input
                  placeholder="Description"
                  value={row.description}
                  onChange={(e) => updateItem(row.id, 'description', e.target.value)}
                  className="col-span-5 rounded-md border border-line px-2 py-1.5 text-sm"
                />
                <input
                  placeholder="Qty (e.g. 10 bag)"
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
                <input
                  type="number"
                  placeholder="Amount"
                  value={row.amount}
                  onChange={(e) => updateItem(row.id, 'amount', e.target.value)}
                  className="col-span-1 rounded-md border border-line px-2 py-1.5 text-sm tabular-nums"
                />
                <button
                  onClick={() => removeRow(row.id)}
                  className="col-span-1 text-xs text-ink-faint hover:text-rust"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <button onClick={addRow} className="mt-2 text-xs font-medium text-ink-light hover:text-ink">
            + Add item
          </button>
        </div>

        <div className="border-t border-line pt-3">
          <p className="mb-2 text-xs font-medium text-ink-faint">Shipping details (optional)</p>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Shipped by">
              <input
                value={shippedBy}
                onChange={(e) => setShippedBy(e.target.value)}
                placeholder="Transport name"
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
        </div>

        <div className="grid grid-cols-3 gap-3 border-t border-line pt-3">
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

        <div className="flex items-center justify-between border-t border-line pt-3 text-sm">
          <span className="text-ink-faint">Grand total</span>
          <span className="font-display text-lg font-semibold tabular-nums text-ink">
            ₹{grandTotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </span>
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating}
          className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          {generating ? 'Generating…' : 'Generate bill'}
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
