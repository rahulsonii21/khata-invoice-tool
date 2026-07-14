const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'khata_token'
const DISPLAY_NAME_KEY = 'khata_display_name'
const COMPANY_NAME_KEY = 'khata_company_name'
const IS_PLATFORM_ADMIN_KEY = 'khata_is_platform_admin'

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY)
}
export function setToken(token, displayName, companyName, isPlatformAdmin) {
  sessionStorage.setItem(TOKEN_KEY, token)
  if (displayName) sessionStorage.setItem(DISPLAY_NAME_KEY, displayName)
  if (companyName) sessionStorage.setItem(COMPANY_NAME_KEY, companyName)
  sessionStorage.setItem(IS_PLATFORM_ADMIN_KEY, isPlatformAdmin ? 'true' : 'false')
}
export function getDisplayName() {
  return sessionStorage.getItem(DISPLAY_NAME_KEY)
}
export function getCompanyName() {
  return sessionStorage.getItem(COMPANY_NAME_KEY)
}
export function getIsPlatformAdmin() {
  return sessionStorage.getItem(IS_PLATFORM_ADMIN_KEY) === 'true'
}
export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(DISPLAY_NAME_KEY)
  sessionStorage.removeItem(COMPANY_NAME_KEY)
  sessionStorage.removeItem(IS_PLATFORM_ADMIN_KEY)
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  let res
  try {
    res = await fetch(`${BASE_URL}${path}`, { headers, ...options })
  } catch (e) {
    // fetch() itself rejecting (as opposed to resolving with a bad status)
    // means a genuine network-level failure - could be no connection, or
    // the service worker had nothing cached to fall back to for this
    // request. Browsers deliberately report this as a generic "Failed to
    // fetch" with no further detail, which was leaking straight through
    // to screens as a raw, unhelpful error message. Treat it the same way
    // as the SW-tagged offline case (same banner) and throw something a
    // person can actually act on instead.
    window.dispatchEvent(new Event('khata-offline-data'))
    throw new Error("Couldn't reach the server — check your connection and try again.")
  }

  // The service worker tags responses it served from its offline cache (used
  // when the network genuinely failed) - surface this so the UI can show a
  // clear "you're viewing cached data" banner rather than silently showing
  // possibly-stale numbers as if they were current.
  if (res.headers.get('X-Served-From-Cache') === 'true') {
    window.dispatchEvent(new Event('khata-offline-data'))
  } else if (res.ok) {
    window.dispatchEvent(new Event('khata-online-data'))
  }

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

  // Monthly reports
  downloadMonthlySummaryPdf: (month, partyId) =>
    downloadFile(`/api/export/monthly/summary-pdf?month=${month}${partyId ? `&party_id=${partyId}` : ''}`),
  downloadMonthlyDetailedExcel: (month, partyId) =>
    downloadFile(`/api/export/monthly/detailed-excel?month=${month}${partyId ? `&party_id=${partyId}` : ''}`),
  downloadMonthlyBillsPdf: (month, partyId) =>
    downloadFile(`/api/export/monthly/bills-pdf?month=${month}${partyId ? `&party_id=${partyId}` : ''}`),

  // Purchase (payables) monthly reports
  downloadMonthlyPurchaseSummaryPdf: (month, supplierId) =>
    downloadFile(`/api/export/monthly/purchase-summary-pdf?month=${month}${supplierId ? `&supplier_id=${supplierId}` : ''}`),
  downloadMonthlyPurchaseDetailedExcel: (month, supplierId) =>
    downloadFile(`/api/export/monthly/purchase-detailed-excel?month=${month}${supplierId ? `&supplier_id=${supplierId}` : ''}`),
  downloadMonthlyPurchaseBillsPdf: (month, supplierId) =>
    downloadFile(`/api/export/monthly/purchase-bills-pdf?month=${month}${supplierId ? `&supplier_id=${supplierId}` : ''}`),

  // Backup
  listBackups: () => request('/api/backup'),
  getDriveStatus: () => request('/api/backup/drive-status'),
  runBackupNow: () => request('/api/backup/run', { method: 'POST' }),
  downloadBackup: (filename) => downloadFile(`/api/backup/${filename}/download`),
  restoreBackup: (filename) => request(`/api/backup/${filename}/restore`, { method: 'POST', body: JSON.stringify({ confirm: 'RESTORE' }) }),

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

  // Suppliers (purchase ledger - payables)
  listSuppliers: () => request('/api/suppliers'),
  getSupplier: (id) => request(`/api/suppliers/${id}`),
  createSupplier: (data) => request('/api/suppliers', { method: 'POST', body: JSON.stringify(data) }),
  updateSupplier: (id, data) => request(`/api/suppliers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteSupplier: (id) => request(`/api/suppliers/${id}`, { method: 'DELETE' }),

  // Purchases
  listPurchases: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/purchases${qs ? `?${qs}` : ''}`)
  },
  getPurchase: (id) => request(`/api/purchases/${id}`),
  createPurchase: (data) => request('/api/purchases', { method: 'POST', body: JSON.stringify(data) }),
  updatePurchase: (id, data) => request(`/api/purchases/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePurchase: (id) => request(`/api/purchases/${id}`, { method: 'DELETE' }),

  // Purchase payments
  addPurchasePayment: (purchaseId, data) =>
    request(`/api/purchases/${purchaseId}/payments`, { method: 'POST', body: JSON.stringify(data) }),
  updatePurchasePayment: (id, data) => request(`/api/purchase-payments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePurchasePayment: (id) => request(`/api/purchase-payments/${id}`, { method: 'DELETE' }),

  // Auth
  getAuthStatus: () => fetch(`${BASE_URL}/api/auth/status`).then((r) => r.json()),
  // Deliberately goes through request() (not a raw fetch, unlike the two
  // above) - that's what makes the online/offline banner able to react to
  // it, since only requests through that pipeline dispatch the events the
  // banner listens for.
  checkHealth: () => request('/api/health'),
  login: (username, password) =>
    fetch(`${BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }).then(async (r) => {
      if (r.status === 401) throw new Error('WRONG_CREDENTIALS')
      if (!r.ok) throw new Error('SERVER_ERROR')
      return r.json()
    }),

  // User accounts (multi-user)
  registerUser: (data) => request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  createInvite: (forNewCompany) => request('/api/auth/invites', { method: 'POST', body: JSON.stringify({ for_new_company: forNewCompany }) }),
  listInvites: () => request('/api/auth/invites'),
  listUsers: () => request('/api/auth/users'),
  deactivateUser: (userId) => request(`/api/auth/users/${userId}`, { method: 'DELETE' }),
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
