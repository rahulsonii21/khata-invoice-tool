import { useEffect, useState } from 'react'
import { api } from '../api'
import { resolveImageUrl } from '../utils'

export default function CompanySettings() {
  const [form, setForm] = useState({
    company_name: '', gstin: '', address: '', phone: '',
    bank_name: '', bank_ifsc: '', bank_account_number: '',
  })
  const [logoUrl, setLogoUrl] = useState(null)
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  function reload() {
    api.getCompanySettings().then((s) => {
      setForm({
        company_name: s.company_name || '',
        gstin: s.gstin || '',
        address: s.address || '',
        phone: s.phone || '',
        bank_name: s.bank_name || '',
        bank_ifsc: s.bank_ifsc || '',
        bank_account_number: s.bank_account_number || '',
      })
      setLogoUrl(s.logo_url || null)
    })
  }

  useEffect(() => {
    reload()
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

  async function handleLogoChange(file) {
    if (!file) return
    setUploadingLogo(true)
    try {
      const updated = await api.uploadCompanyLogo(file)
      setLogoUrl(updated.logo_url || null)
    } finally {
      setUploadingLogo(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      <header className="mb-6">
        <h1 className="font-display text-2xl font-semibold text-ink">Your Business Details</h1>
        <p className="mt-1 text-sm text-ink-faint">
          Appears as the letterhead on PDF statements and generated bills.
        </p>
      </header>

      <div className="space-y-3 rounded-lg border border-line bg-white p-4">
        <Field label="Logo">
          <div className="flex items-center gap-3">
            {logoUrl && (
              <img
                src={resolveImageUrl(logoUrl)}
                alt="Logo"
                className="h-16 w-16 rounded-md border border-line object-contain bg-white"
              />
            )}
            <label className="cursor-pointer rounded-md border border-line px-3 py-2 text-sm text-ink-faint hover:bg-sage/30">
              {uploadingLogo ? 'Uploading…' : logoUrl ? 'Change logo' : 'Upload logo'}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => handleLogoChange(e.target.files[0])}
              />
            </label>
          </div>
        </Field>

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

        <div className="border-t border-line pt-3">
          <p className="mb-2 text-xs font-medium text-ink-faint">
            Bank details (shown on generated bills)
          </p>
          <div className="space-y-3">
            <Field label="Bank name & branch">
              <input
                className="w-full rounded-md border border-line px-3 py-2 text-sm"
                value={form.bank_name}
                onChange={(e) => update('bank_name', e.target.value)}
              />
            </Field>
            <Field label="IFSC code">
              <input
                className="w-full rounded-md border border-line px-3 py-2 text-sm"
                value={form.bank_ifsc}
                onChange={(e) => update('bank_ifsc', e.target.value)}
              />
            </Field>
            <Field label="Account number">
              <input
                className="w-full rounded-md border border-line px-3 py-2 text-sm"
                value={form.bank_account_number}
                onChange={(e) => update('bank_account_number', e.target.value)}
              />
            </Field>
          </div>
        </div>

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
