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
  paid: { label: 'Paid', className: 'text-leaf bg-leaf/10' },
  partially_paid: { label: 'Partial', className: 'text-marigold bg-marigold/10' },
  unpaid: { label: 'Due', className: 'text-rust bg-rust/10' },
  overdue: { label: 'Overdue', className: 'text-paper bg-rust' },
}

// Picks the right status style, upgrading to "overdue" styling when applicable
// without needing a separate backend status value.
export function getStatusStyle(invoice) {
  if (invoice.is_overdue) return STATUS_STYLES.overdue
  return STATUS_STYLES[invoice.status] || STATUS_STYLES.unpaid
}

// Formats an Indian phone number for wa.me links - assumes India (+91) if
// no country code is already present, strips spaces/dashes/parens.
export function formatPhoneForWhatsApp(phone) {
  if (!phone) return null
  const digits = phone.replace(/[^\d]/g, '')
  if (digits.length === 10) return `91${digits}`
  if (digits.length === 12 && digits.startsWith('91')) return digits
  return digits
}

export function openWhatsAppMessage(phone, message) {
  const formattedPhone = formatPhoneForWhatsApp(phone)
  const url = formattedPhone
    ? `https://wa.me/${formattedPhone}?text=${encodeURIComponent(message)}`
    : `https://wa.me/?text=${encodeURIComponent(message)}`
  window.open(url, '_blank')
}

// Shares a file via the native share sheet (WhatsApp shows up as an option
// on mobile) when supported; falls back to a plain download otherwise, since
// desktop browsers and some mobile browsers don't support file sharing.
export async function shareOrDownloadFile(blob, filename, shareTitle) {
  const file = new File([blob], filename, { type: blob.type })

  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: shareTitle })
      return 'shared'
    } catch (e) {
      if (e.name === 'AbortError') return 'cancelled'
      // fall through to download on any other share failure
    }
  }

  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return 'downloaded'
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// raw_image_url is either a full Supabase URL or a relative local-disk path
// (e.g. "/files/invoices/xxx.jpg") depending on how storage is configured.
export function resolveImageUrl(rawUrl) {
  if (!rawUrl) return null
  if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) return rawUrl
  return `${API_BASE}${rawUrl}`
}
