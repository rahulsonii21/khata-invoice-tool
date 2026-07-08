import { useState, useEffect, useRef } from 'react'

export default function PartyAutocomplete({ value, onChange, parties }) {
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  const matches = value
    ? parties.filter((p) => p.name.toLowerCase().includes(value.toLowerCase()))
    : parties

  useEffect(() => {
    function handleClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const isNewParty = value && !parties.some((p) => p.name.toLowerCase() === value.toLowerCase())

  return (
    <div className="relative" ref={wrapRef}>
      <div className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          placeholder={parties.length > 0 ? 'Type new, or click to pick existing party' : 'Party name'}
          className="w-full rounded-md border border-line bg-white px-3 py-2 pr-9 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-ink/30"
        />
        {parties.length > 0 && (
          <button
            type="button"
            tabIndex={-1}
            onClick={() => setOpen((o) => !o)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink"
          >
            ▾
          </button>
        )}
      </div>
      {isNewParty && (
        <span className="mt-1 inline-block text-xs text-marigold font-medium">
          Will create new party "{value}"
        </span>
      )}
      {open && matches.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-md border border-line bg-white shadow-md">
          {!value && (
            <li className="px-3 py-1.5 text-xs font-medium text-ink-faint">Existing parties</li>
          )}
          {matches.map((p) => (
            <li
              key={p.id}
              className="cursor-pointer px-3 py-2 text-sm text-ink hover:bg-sage"
              onClick={() => {
                onChange(p.name)
                setOpen(false)
              }}
            >
              {p.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
