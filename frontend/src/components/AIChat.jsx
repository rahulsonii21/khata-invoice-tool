import { useState, useRef, useEffect } from 'react'
import { api } from '../api'
import { openWhatsAppMessage } from '../utils'
import VoiceChat from './VoiceChat'

const SUGGESTIONS = [
  'How much is outstanding?',
  "What's overdue?",
  'Check stock for [item name]',
  "What's 5% of 2,50,000?",
]

export default function AIChat() {
  const [voiceMode, setVoiceMode] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function send(text) {
    const messageText = (text ?? input).trim()
    if (!messageText || sending) return

    setError(null)
    setInput('')
    const nextMessages = [...messages, { role: 'user', text: messageText }]
    setMessages(nextMessages)
    setSending(true)

    try {
      const res = await api.aiChat(nextMessages)
      setMessages([...nextMessages, { role: 'model', text: res.reply, toolCalls: res.tool_calls }])
    } catch (e) {
      setError(e.message)
      setMessages(nextMessages) // keep the user's message visible even if the reply failed
    } finally {
      setSending(false)
    }
  }

  if (voiceMode) {
    return (
      <div className="relative">
        <button
          onClick={() => setVoiceMode(false)}
          className="absolute right-4 top-4 z-10 rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-ink hover:bg-sage/40"
        >
          ← Text chat
        </button>
        <VoiceChat />
      </div>
    )
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-2xl flex-col px-4 py-6">
      <header className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink">Lekha AI</h1>
          <p className="mt-1 text-sm text-ink-faint">
            Ask about balances, stock, or do a calculation. Text only for now, and read-only - it can look things up but can't yet create or change anything.
          </p>
        </div>
        <button
          onClick={() => setVoiceMode(true)}
          className="shrink-0 rounded-full bg-ink px-3 py-2 text-sm text-paper hover:bg-ink-light"
          title="Talk to Lekha"
        >
          🎙️
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-line bg-white p-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm text-ink-faint">Try asking:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-line px-3 py-1.5 text-xs text-ink hover:bg-sage/40"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                m.role === 'user' ? 'bg-ink text-paper' : 'bg-sage/40 text-ink'
              }`}
            >
              {m.toolCalls && m.toolCalls.length > 0 && (
                <div className="mb-1.5 flex flex-wrap gap-1">
                  {m.toolCalls.map((tc, j) => (
                    <span key={j} className="rounded-full bg-white/60 px-2 py-0.5 text-[10px] text-ink-faint">
                      🔎 {tc.name.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}
              <p className="whitespace-pre-wrap">{m.text}</p>
              {(() => {
                const reminder = m.toolCalls?.find(
                  (tc) => tc.name === 'draft_payment_reminder' && tc.result?.can_send
                )
                if (!reminder) return null
                return (
                  <button
                    onClick={() => openWhatsAppMessage(reminder.result.phone, reminder.result.draft_message)}
                    className="mt-2 flex items-center gap-1.5 rounded-md bg-[#25D366] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#20bd5a]"
                  >
                    Send via WhatsApp
                  </button>
                )
              })()}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-sage/40 px-3 py-2 text-sm text-ink-faint">Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="mt-2 rounded-md bg-rust/10 px-3 py-2 text-sm text-rust">{error}</p>}

      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask anything…"
          disabled={sending}
          className="flex-1 rounded-md border border-line px-3 py-2 text-sm disabled:opacity-50"
        />
        <button
          onClick={() => send()}
          disabled={sending || !input.trim()}
          className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-paper hover:bg-ink-light disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}
