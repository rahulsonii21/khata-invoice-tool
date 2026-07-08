import { useEffect, useState } from 'react'
import { api } from '../api'

export default function CompanySettings() {
  const [form, setForm] = useState({ company_name: '', gstin: '', address: '', phone: '' })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.getCompanySettings().then((s) =>
      setForm({
        company_name: s.company_name || '',
        gstin: s.gstin || '',
        address: s.address || '',
        phone: s.phone || '',
      })
    )
  }, [])

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
    setSaved(false)
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.updateCompanySettings(form)
      setSaved(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Your Business Details</h1>
        <p className="mt-1 text-sm text-ink-faint">
          Appears as the letterhead on PDF statements you export.
        </p>
      </header>

      <div className="space-y-3 rounded-lg border border-line bg-white p-4">
        <Field label="Company / business name">
          <input
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
            value={form.company_name}
            onChange={(e) => update('company_name', e.target.value)}
          />
        </Field>
        <Field label="GSTIN">
          <input
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
            value={form.gstin}
            onChange={(e) => update('gstin', e.target.value)}
          />
        </Field>
        <Field label="Address">
          <textarea
            rows={2}
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
            value={form.address}
            onChange={(e) => update('address', e.target.value)}
          />
        </Field>
        <Field label="Phone">
          <input
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
            value={form.phone}
            onChange={(e) => update('phone', e.target.value)}
          />
        </Field>

        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full rounded-md bg-ink py-2.5 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save'}
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
