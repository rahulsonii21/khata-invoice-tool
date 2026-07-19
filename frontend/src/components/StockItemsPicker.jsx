import { useEffect, useState } from 'react'
import { api } from '../api'

/**
 * Lets someone optionally record "this stock item, from this location,
 * this many units" against a sale. Entirely optional - if nothing is
 * added here, the invoice/bill behaves exactly as it always has.
 *
 * value: array of { item_id, location_id, quantity }
 * onChange: (newValue) => void
 */
export default function StockItemsPicker({ value, onChange }) {
  const [items, setItems] = useState([])
  const [locations, setLocations] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    Promise.all([api.listItems(), api.listStockLocations()])
      .then(([its, locs]) => {
        setItems(its)
        setLocations(locs)
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }, [])

  // Nothing to link against yet (no items or no locations set up) - stay
  // out of the way entirely rather than showing an empty, confusing picker
  if (!loaded || items.length === 0 || locations.length === 0) {
    return null
  }

  function addRow() {
    onChange([...value, { item_id: items[0].id, location_id: locations[0].id, quantity: '' }])
  }

  function updateRow(idx, field, val) {
    const next = [...value]
    next[idx] = { ...next[idx], [field]: val }
    onChange(next)
  }

  function removeRow(idx) {
    onChange(value.filter((_, i) => i !== idx))
  }

  return (
    <div className="rounded-lg border border-line bg-sage/20 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-ink">Deduct from stock (optional)</span>
        <button onClick={addRow} className="text-xs font-medium text-ink-light hover:underline">
          + Add item sold
        </button>
      </div>

      {value.length === 0 && (
        <p className="text-xs text-ink-faint">
          Link items sold here to automatically deduct stock - leave blank to skip.
        </p>
      )}

      <div className="space-y-2">
        {value.map((row, idx) => (
          <div key={idx} className="flex flex-wrap items-center gap-2">
            <select
              value={row.item_id}
              onChange={(e) => updateRow(idx, 'item_id', e.target.value)}
              className="rounded-md border border-line px-2 py-1.5 text-sm"
            >
              {items.map((it) => (
                <option key={it.id} value={it.id}>{it.name}</option>
              ))}
            </select>
            <select
              value={row.location_id}
              onChange={(e) => updateRow(idx, 'location_id', e.target.value)}
              className="rounded-md border border-line px-2 py-1.5 text-sm"
            >
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>{loc.name}</option>
              ))}
            </select>
            <input
              type="number"
              value={row.quantity}
              onChange={(e) => updateRow(idx, 'quantity', e.target.value)}
              placeholder="Qty"
              className="w-20 rounded-md border border-line px-2 py-1.5 text-sm"
            />
            <button onClick={() => removeRow(idx)} className="text-xs font-medium text-rust hover:underline">
              Remove
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Converts the picker's rows into the shape the API expects, dropping
 * any rows that don't have a real quantity yet (still being filled in). */
export function stockItemsForPayload(rows) {
  return rows
    .filter((r) => r.quantity && parseFloat(r.quantity) > 0)
    .map((r) => ({ item_id: r.item_id, location_id: r.location_id, quantity: parseFloat(r.quantity) }))
}
