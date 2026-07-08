export function formatINR(amount) {
  if (amount == null || isNaN(amount)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(amount)
}

export function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (isNaN(d)) return dateStr
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export const STATUS_STYLES = {
  paid: { label: 'Paid', className: 'text-ink-light bg-sage' },
  partially_paid: { label: 'Partial', className: 'text-marigold bg-marigold/10' },
  unpaid: { label: 'Due', className: 'text-rust bg-rust/10' },
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// raw_image_url is either a full Supabase URL or a relative local-disk path
// (e.g. "/files/invoices/xxx.jpg") depending on how storage is configured.
export function resolveImageUrl(rawUrl) {
  if (!rawUrl) return null
  if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) return rawUrl
  return `${API_BASE}${rawUrl}`
}
