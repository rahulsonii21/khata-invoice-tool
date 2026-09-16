import { useState, useRef, useCallback } from 'react'
import { getToken } from '../api'

// Gemini Live audio format, per the documented protocol - input and
// output use DIFFERENT sample rates, which is why capture and playback
// each get their own AudioContext below.
const INPUT_SAMPLE_RATE = 16000
const OUTPUT_SAMPLE_RATE = 24000

const STATES = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  LISTENING: 'listening',
  THINKING: 'thinking',
  SPEAKING: 'speaking',
  ERROR: 'error',
}

export default function VoiceChat() {
  const [state, setState] = useState(STATES.IDLE)
  const [transcript, setTranscript] = useState([])
  const [errorMsg, setErrorMsg] = useState(null)
  const [activeTool, setActiveTool] = useState(null)

  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const processorRef = useRef(null)
  const micStreamRef = useRef(null)
  const playbackContextRef = useRef(null)
  const playbackQueueTimeRef = useRef(0)

  const addLine = useCallback((role, text) => {
    if (!text) return
    setTranscript((t) => [...t, { role, text }])
  }, [])

  function floatTo16BitPCM(float32Array) {
    const buffer = new ArrayBuffer(float32Array.length * 2)
    const view = new DataView(buffer)
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]))
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true) // little-endian
    }
    return buffer
  }

  function arrayBufferToBase64(buffer) {
    let binary = ''
    const bytes = new Uint8Array(buffer)
    for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i])
    return btoa(binary)
  }

  function base64ToInt16Array(base64) {
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    return new Int16Array(bytes.buffer)
  }

  function playAudioChunk(base64Data) {
    if (!playbackContextRef.current) {
      playbackContextRef.current = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: OUTPUT_SAMPLE_RATE,
      })
      playbackQueueTimeRef.current = playbackContextRef.current.currentTime
    }
    const ctx = playbackContextRef.current
    const int16 = base64ToInt16Array(base64Data)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768

    const buffer = ctx.createBuffer(1, float32.length, OUTPUT_SAMPLE_RATE)
    buffer.copyToChannel(float32, 0)

    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(ctx.destination)

    // Queue chunks back-to-back rather than all starting at "now", so
    // audio plays as one continuous stream instead of overlapping or
    // gapping depending on how fast chunks arrive.
    const startAt = Math.max(playbackQueueTimeRef.current, ctx.currentTime)
    source.start(startAt)
    playbackQueueTimeRef.current = startAt + buffer.duration
  }

  async function start() {
    setErrorMsg(null)
    setTranscript([])
    setState(STATES.CONNECTING)

    try {
      micStreamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      setErrorMsg('Microphone access was denied or unavailable.')
      setState(STATES.ERROR)
      return
    }

    const base = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/^http/, 'ws')
    const token = getToken() || ''
    const ws = new WebSocket(`${base}/api/ai/live/ws?token=${encodeURIComponent(token)}`)
    wsRef.current = ws

    ws.onopen = () => {
      // Set up microphone capture once the socket is open. AudioContext
      // is created at the INPUT rate directly - most browsers will
      // resample the actual hardware capture to match automatically.
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: INPUT_SAMPLE_RATE })
      audioContextRef.current = audioCtx
      const source = audioCtx.createMediaStreamSource(micStreamRef.current)

      // ScriptProcessorNode is deprecated in favor of AudioWorklet, but
      // remains universally supported and is simple to use inline without
      // a separate worklet file - a reasonable tradeoff here given this
      // needs to work reliably on Android Chrome specifically.
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return
        const pcm = floatTo16BitPCM(e.inputBuffer.getChannelData(0))
        ws.send(JSON.stringify({ audio: arrayBufferToBase64(pcm) }))
      }
      source.connect(processor)
      processor.connect(audioCtx.destination)

      setState(STATES.LISTENING)
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.error) {
        setErrorMsg(msg.error)
        setState(STATES.ERROR)
        return
      }

      if (msg.tool_call) {
        setActiveTool(msg.tool_call.name)
        setState(STATES.THINKING)
        return
      }

      if (msg.serverContent) {
        const sc = msg.serverContent
        if (sc.interrupted) {
          playbackQueueTimeRef.current = 0
        }
        if (sc.inputTranscription?.text) {
          addLine('user', sc.inputTranscription.text)
        }
        if (sc.outputTranscription?.text) {
          addLine('model', sc.outputTranscription.text)
        }
        const parts = sc.modelTurn?.parts || []
        for (const part of parts) {
          if (part.inlineData?.data) {
            setState(STATES.SPEAKING)
            playAudioChunk(part.inlineData.data)
          }
          if (part.text) {
            addLine('model', part.text)
          }
        }
        if (sc.turnComplete) {
          setActiveTool(null)
          setState(STATES.LISTENING)
        }
      }
    }

    ws.onerror = () => {
      setErrorMsg('Connection to the voice service failed.')
      setState(STATES.ERROR)
    }

    ws.onclose = () => {
      stop()
    }
  }

  function stop() {
    processorRef.current?.disconnect()
    audioContextRef.current?.close()
    micStreamRef.current?.getTracks().forEach((t) => t.stop())
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) wsRef.current.close()
    processorRef.current = null
    audioContextRef.current = null
    micStreamRef.current = null
    wsRef.current = null
    setState(STATES.IDLE)
    setActiveTool(null)
  }

  const stateLabel = {
    [STATES.IDLE]: 'Tap to talk',
    [STATES.CONNECTING]: 'Connecting…',
    [STATES.LISTENING]: 'Listening…',
    [STATES.THINKING]: activeTool ? `Checking ${activeTool.replace(/_/g, ' ')}…` : 'Thinking…',
    [STATES.SPEAKING]: 'Speaking…',
    [STATES.ERROR]: 'Something went wrong',
  }[state]

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-2xl flex-col items-center px-4 py-6">
      <header className="mb-4 text-center">
        <h1 className="font-display text-2xl font-semibold text-ink">Talk to Lekha</h1>
        <p className="mt-1 text-sm text-ink-faint">Voice, powered by Gemini Live. Speak naturally in English or Hindi.</p>
      </header>

      <div className="flex flex-1 flex-col items-center justify-center gap-4">
        <button
          onClick={state === STATES.IDLE || state === STATES.ERROR ? start : stop}
          className={`flex h-24 w-24 items-center justify-center rounded-full text-3xl text-white shadow-lg transition-colors ${
            state === STATES.LISTENING
              ? 'animate-pulse bg-rust'
              : state === STATES.IDLE || state === STATES.ERROR
                ? 'bg-ink hover:bg-ink-light'
                : 'bg-marigold'
          }`}
        >
          {state === STATES.IDLE || state === STATES.ERROR ? '🎙️' : '⏹️'}
        </button>
        <p className="text-sm font-medium text-ink-faint">{stateLabel}</p>
        {errorMsg && <p className="max-w-xs text-center text-sm text-rust">{errorMsg}</p>}
      </div>

      <div className="w-full space-y-2 overflow-y-auto rounded-lg border border-line bg-white p-3" style={{ maxHeight: '30vh' }}>
        {transcript.length === 0 && <p className="text-center text-xs text-ink-faint">Transcript will appear here</p>}
        {transcript.map((line, i) => (
          <p key={i} className={`text-sm ${line.role === 'user' ? 'text-ink' : 'text-ink-light'}`}>
            <span className="font-medium">{line.role === 'user' ? 'You: ' : 'Lekha: '}</span>
            {line.text}
          </p>
        ))}
      </div>
    </div>
  )
}
