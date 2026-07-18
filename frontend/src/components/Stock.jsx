import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Stock() {
  const [locations, setLocations] = useState([])
  const [items, setItems] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [showNewItem, setShowNewItem] = useState(false)
  const [showNewLocation, setShowNewLocation] = useState(false)
  const [filterLocationId, setFilterLocationId] = useState(null) // null = show all locations

  function reload() {
    setLoadError(null)
    Promise.all([api.listStockLocations(), api.listItems()])
      .then(([locs, its]) => {
        setLocations(locs)
        setItems(its)
      })
      .catch((e) => setLoadError(e.message))
  }

  useEffect(() => {
    reload()
  }, [])

  async function removeLocation(location) {
    if (!confirm(`Remove "${location.name}"? Any stock recorded there will be removed too - stock at your other places is untouched.`)) return
    try {
      await api.deleteStockLocation(location.id)
      if (filterLocationId === location.id) setFilterLocationId(null)
      reload()
    } catch (e) {
      alert(e.message)
    }
  }

  const visibleLocations = filterLocationId
    ? locations.filter((l) => l.id === filterLocationId)
    : locations

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Stock</h1>
          <p className="mt-1 text-sm text-ink-faint">What's actually on hand, across every place you keep it.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowNewLocation((s) => !s)}
            className="rounded-md border border-ink/30 px-3 py-2 text-sm font-medium text-ink hover:bg-sage"
          >
            + Location
          </button>
          <button
            onClick={() => setShowNewItem((s) => !s)}
            className="rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper hover:bg-ink-light"
          >
            + Item
          </button>
        </div>
      </header>

      {loadError && (
        <div className="mb-4 flex items-center justify-between rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">
          <span>{loadError}</span>
          <button onClick={reload} className="font-medium underline hover:no-underline">
            Try again
          </button>
        </div>
      )}

      {showNewLocation && (
        <NewLocationForm
          onDone={() => {
            setShowNewLocation(false)
            reload()
          }}
          onCancel={() => setShowNewLocation(false)}
        />
      )}

      {showNewItem && (
        <NewItemForm
          onDone={() => {
            setShowNewItem(false)
            reload()
          }}
          onCancel={() => setShowNewItem(false)}
        />
      )}

      {locations.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button
            onClick={() => setFilterLocationId(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium ${
              filterLocationId === null ? 'bg-ink text-paper' : 'border border-line text-ink-faint hover:bg-sage'
            }`}
          >
            All locations
          </button>
          {locations.map((loc) => (
            <button
              key={loc.id}
              onClick={() => setFilterLocationId(loc.id)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                filterLocationId === loc.id ? 'bg-ink text-paper' : 'border border-line text-ink-faint hover:bg-sage'
              }`}
            >
              {loc.name}
            </button>
          ))}
        </div>
      )}

      {filterLocationId && (
        <button
          onClick={() => removeLocation(locations.find((l) => l.id === filterLocationId))}
          className="mb-3 text-xs font-medium text-rust hover:underline"
        >
          Remove "{locations.find((l) => l.id === filterLocationId)?.name}"
        </button>
      )}

      {locations.length === 0 ? (
        <p className="rounded-lg border border-line bg-white p-4 text-sm text-ink-faint">
          Add your first location (like "Shop" or a godown name) to get started.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-line bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-sage/40 text-left text-xs font-medium text-ink-faint">
                <th className="px-4 py-2">Item</th>
                {visibleLocations.map((loc) => (
                  <th key={loc.id} className="px-4 py-2 text-right whitespace-nowrap">{loc.name}</th>
                ))}
                {!filterLocationId && <th className="px-4 py-2 text-right">Total</th>}
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr>
                  <td colSpan={visibleLocations.length + 2} className="px-4 py-6 text-center text-ink-faint">
                    No items yet.
                  </td>
                </tr>
              )}
              {items.map((item) => (
                <ItemRow key={item.id} item={item} locations={visibleLocations} showTotal={!filterLocationId} onChanged={reload} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ItemRow({ item, locations, showTotal, onChanged }) {
  const quantityFor = (locationId) => {
    const entry = item.stock_by_location.find((s) => s.location_id === locationId)
    return entry ? entry.quantity : 0
  }

  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-4 py-3">
        <div className="font-medium text-ink">{item.name}</div>
        {item.unit && <div className="text-xs text-ink-faint">{item.unit}</div>}
      </td>
      {locations.map((loc) => (
        <td key={loc.id} className="px-2 py-2 text-right">
          <EditableQuantity
            value={quantityFor(loc.id)}
            onSave={async (qty) => {
              await api.setItemStock(item.id, loc.id, qty)
              onChanged()
            }}
          />
        </td>
      ))}
      {showTotal && (
        <td
          className={`px-4 py-3 text-right font-medium tabular-nums ${
            item.is_low_stock ? 'text-rust' : 'text-ink'
          }`}
        >
          {item.total_quantity}
          {item.is_low_stock && <div className="text-xs font-normal">low stock</div>}
        </td>
      )}
    </tr>
  )
}

function EditableQuantity({ value, onSave }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [saving, setSaving] = useState(false)

  if (!editing) {
    return (
      <button
        onClick={() => {
          setDraft(value)
          setEditing(true)
        }}
        className="w-16 rounded px-2 py-1 text-right tabular-nums text-ink hover:bg-sage/40"
      >
        {value}
      </button>
    )
  }

  async function save() {
    const num = parseFloat(draft)
    if (isNaN(num) || num < 0) {
      setEditing(false)
      return
    }
    setSaving(true)
    await onSave(num)
    setSaving(false)
    setEditing(false)
  }

  return (
    <input
      autoFocus
      type="number"
      value={draft}
      disabled={saving}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => e.key === 'Enter' && save()}
      className="w-16 rounded-md border border-ink/40 px-2 py-1 text-right text-sm"
    />
  )
}

function NewLocationForm({ onDone, onCancel }) {
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function submit() {
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      await api.createStockLocation({ name: name.trim() })
      onDone()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-4 flex gap-2 rounded-lg border border-line bg-white p-3">
      <div className="flex-1">
        {error && <p className="mb-2 text-xs text-rust">{error}</p>}
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="Location name (e.g. Shop, Bholiyawas Godown)"
          className="w-full rounded-md border border-line px-3 py-2 text-sm"
        />
      </div>
      <button
        onClick={submit}
        disabled={saving}
        className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
      >
        {saving ? 'Adding…' : 'Add'}
      </button>
      <button onClick={onCancel} className="rounded-md border border-line px-3 py-2 text-sm text-ink-faint">
        Cancel
      </button>
    </div>
  )
}

function NewItemForm({ onDone, onCancel }) {
  const [name, setName] = useState('')
  const [unit, setUnit] = useState('')
  const [threshold, setThreshold] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function submit() {
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      await api.createItem({
        name: name.trim(),
        unit: unit.trim() || null,
        reorder_threshold: threshold ? parseFloat(threshold) : null,
      })
      onDone()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-4 flex flex-wrap gap-2 rounded-lg border border-line bg-white p-3">
      <div className="min-w-[150px] flex-1">
        {error && <p className="mb-2 text-xs text-rust">{error}</p>}
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="Item name (e.g. DAP Fertilizer)"
          className="w-full rounded-md border border-line px-3 py-2 text-sm"
        />
      </div>
      <input
        value={unit}
        onChange={(e) => setUnit(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Unit (bag, kg…)"
        className="w-32 rounded-md border border-line px-3 py-2 text-sm"
      />
      <input
        type="number"
        value={threshold}
        onChange={(e) => setThreshold(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Alert below…"
        className="w-32 rounded-md border border-line px-3 py-2 text-sm"
      />
      <button
        onClick={submit}
        disabled={saving}
        className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
      >
        {saving ? 'Adding…' : 'Add'}
      </button>
      <button onClick={onCancel} className="rounded-md border border-line px-3 py-2 text-sm text-ink-faint">
        Cancel
      </button>
    </div>
  )
}
