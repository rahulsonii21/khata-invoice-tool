const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Parties
  listParties: () => request('/api/parties'),
  getParty: (id) => request(`/api/parties/${id}`),
  createParty: (data) => request('/api/parties', { method: 'POST', body: JSON.stringify(data) }),
  updateParty: (id, data) => request(`/api/parties/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Invoices
  listInvoices: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/invoices${qs ? `?${qs}` : ''}`)
  },
  getInvoice: (id) => request(`/api/invoices/${id}`),
  createInvoice: (data) => request('/api/invoices', { method: 'POST', body: JSON.stringify(data) }),
  updateInvoice: (id, data) => request(`/api/invoices/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteInvoice: (id) => request(`/api/invoices/${id}`, { method: 'DELETE' }),

  // Payments
  addPayment: (invoiceId, data) =>
    request(`/api/invoices/${invoiceId}/payments`, { method: 'POST', body: JSON.stringify(data) }),
  updatePayment: (id, data) => request(`/api/payments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePayment: (id) => request(`/api/payments/${id}`, { method: 'DELETE' }),

  // Dashboard
  getSummary: () => request('/api/dashboard/summary'),

  // OCR
  extractInvoice: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/ocr/extract', { method: 'POST', body: form })
  },

  // Export - these trigger a file download rather than returning JSON
  downloadPartyPdf: (partyId) => downloadFile(`/api/export/party/${partyId}/pdf`),
  downloadPartyExcel: (partyId) => downloadFile(`/api/export/party/${partyId}/excel`),
  downloadAllExcel: () => downloadFile('/api/export/all/excel'),

  // Backup
  listBackups: () => request('/api/backup'),
  runBackupNow: () => request('/api/backup/run', { method: 'POST' }),
  downloadBackup: (filename) => downloadFile(`/api/backup/${filename}/download`),
}

async function downloadFile(path) {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)

  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="(.+)"/)
  const filename = match ? match[1] : 'export'

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
