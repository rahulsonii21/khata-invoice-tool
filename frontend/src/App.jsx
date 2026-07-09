import { useState, useEffect } from 'react'
import UploadReview from './components/UploadReview'
import Dashboard from './components/Dashboard'
import PartyList from './components/PartyList'
import PartyDetail from './components/PartyDetail'
import Backups from './components/Backups'
import CompanySettings from './components/CompanySettings'
import GenerateBill from './components/GenerateBill'
import Login from './components/Login'
import { api, getToken } from './api'

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'upload', label: 'Upload' },
  { id: 'bill', label: 'Generate Bill' },
  { id: 'parties', label: 'Parties' },
  { id: 'backups', label: 'Backups' },
  { id: 'settings', label: 'Settings' },
]

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [openPartyId, setOpenPartyId] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [needsLogin, setNeedsLogin] = useState(false)

  function checkAuth() {
    api.getAuthStatus().then((status) => {
      setNeedsLogin(status.required && !getToken())
      setAuthChecked(true)
    })
  }

  useEffect(() => {
    checkAuth()
    // Any 401 anywhere in the app re-triggers the login screen
    const handler = () => setNeedsLogin(true)
    window.addEventListener('khata-auth-required', handler)
    return () => window.removeEventListener('khata-auth-required', handler)
  }, [])

  function openParty(id) {
    setOpenPartyId(id)
    setTab('parties')
  }

  if (!authChecked) {
    return <div className="flex min-h-screen items-center justify-center bg-paper text-sm text-ink-faint">Loading…</div>
  }

  if (needsLogin) {
    return <Login onSuccess={() => setNeedsLogin(false)} />
  }

  return (
    <div className="min-h-screen bg-paper pb-16 sm:pb-0">
      <nav className="border-b border-line bg-white px-4 py-3">
        <div className="mx-auto flex max-w-5xl items-center gap-4 overflow-x-auto">
          <div className="flex flex-shrink-0 items-center gap-2">
            <span className="stamp px-2 py-0.5 text-xs font-semibold text-ink">खाता</span>
            <span className="font-display text-lg font-semibold text-ink">Khata</span>
          </div>
          <div className="hidden gap-1 sm:flex">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setTab(t.id)
                  if (t.id !== 'parties') setOpenPartyId(null)
                }}
                className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ${
                  tab === t.id ? 'bg-ink text-paper' : 'text-ink-faint hover:bg-sage'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {tab === 'dashboard' && <Dashboard onOpenParty={openParty} />}
      {tab === 'upload' && <UploadReview />}
      {tab === 'bill' && <GenerateBill />}
      {tab === 'parties' &&
        (openPartyId ? (
          <PartyDetail partyId={openPartyId} onBack={() => setOpenPartyId(null)} />
        ) : (
          <PartyList onOpenParty={setOpenPartyId} />
        ))}
      {tab === 'backups' && <Backups />}
      {tab === 'settings' && <CompanySettings />}

      {/* Mobile bottom tab bar */}
      <div className="fixed inset-x-0 bottom-0 flex overflow-x-auto border-t border-line bg-white sm:hidden">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => {
              setTab(t.id)
              if (t.id !== 'parties') setOpenPartyId(null)
            }}
            className={`flex-1 whitespace-nowrap px-2 py-3 text-xs font-medium ${
              tab === t.id ? 'text-ink' : 'text-ink-faint'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  )
}
