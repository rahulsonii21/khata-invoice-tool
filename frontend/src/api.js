const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'khata_token'

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY)
}
export function setToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token)
}
export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY)
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, { headers, ...options })

  if (res.status === 401) {
    // Session expired or invalid - clear it and force back to the login screen
    clearToken()
    window.dispatchEvent(new Event('khata-auth-required'))
    throw new Error('Session expired - please log in again')
  }

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

  // Plain image upload (no OCR) - used when attaching a photo during manual entry
  uploadImage: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/uploads/image', { method: 'POST', body: form })
  },

  // Export - these trigger a file download rather than returning JSON
  downloadPartyPdf: (partyId) => downloadFile(`/api/export/party/${partyId}/pdf`),
  downloadPartyExcel: (partyId) => downloadFile(`/api/export/party/${partyId}/excel`),
  downloadAllExcel: () => downloadFile('/api/export/all/excel'),

  // Backup
  listBackups: () => request('/api/backup'),
  runBackupNow: () => request('/api/backup/run', { method: 'POST' }),
  downloadBackup: (filename) => downloadFile(`/api/backup/${filename}/download`),

  // Company settings
  getCompanySettings: () => request('/api/settings/company'),
  updateCompanySettings: (data) => request('/api/settings/company', { method: 'PUT', body: JSON.stringify(data) }),
  uploadCompanyLogo: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/settings/company/logo', { method: 'POST', body: form })
  },

  // Bill generation
  generateBill: (data) => request('/api/bills/generate', { method: 'POST', body: JSON.stringify(data) }),
  regenerateBill: (invoiceId, data) => request(`/api/bills/${invoiceId}/regenerate`, { method: 'PUT', body: JSON.stringify(data) }),

  // Auth
  getAuthStatus: () => fetch(`${BASE_URL}/api/auth/status`).then((r) => r.json()),
  login: (pin) =>
    fetch(`${BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    }).then(async (r) => {
      if (!r.ok) throw new Error('Incorrect PIN')
      return r.json()
    }),
}

export async function fetchFileBlob(path) {
  const token = getToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(`${BASE_URL}${path}`, { headers })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="(.+)"/)
  const filename = match ? match[1] : 'file'
  const blob = await res.blob()
  return { blob, filename }
}

async function downloadFile(path) {
  const token = getToken()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(`${BASE_URL}${path}`, { headers })
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
