import { useState, useRef, useEffect, useCallback } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Send, Bot, User, CheckCircle2, AlertTriangle, Loader2, FileText, ChevronDown, X, Zap, Sparkles } from 'lucide-react'
import { askQuestion, getFilings, getCompanies } from '../services/api'
import { ConfidenceBadge } from '../components/StatusBadge'

const STARTERS = [
  'What was the total revenue this year?',
  'What are the key risk factors?',
  'How did profit after tax change vs prior year?',
  'Summarize the management outlook.',
  'Are there any contingent liabilities?',
  'What were the major capital expenditures?',
]

function renderAnswer(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith('**') && p.endsWith('**')
      ? <strong key={i} className="font-bold text-slate-100">{p.slice(2,-2)}</strong>
      : <span key={i}>{p}</span>
  )
}

function Message({ msg, onSuggest }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'} animate-in`}>
      {!isUser && (
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center flex-shrink-0 mt-1 shadow-lg shadow-orange-500/20">
          <Bot className="w-5 h-5 text-white" />
        </div>
      )}
      <div className={`max-w-2xl flex flex-col gap-3 ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/20 rounded-br-md'
            : 'bg-[#0F1419]/80 backdrop-blur-md border border-white/[0.08] text-slate-300 rounded-bl-md'
        }`}>
          {isUser ? (
            <p className="whitespace-pre-wrap">{msg.content}</p>
          ) : (
            <p className="whitespace-pre-wrap">{renderAnswer(msg.content)}</p>
          )}
        </div>

        {/* Citations */}
        {msg.citations?.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {msg.citations.map((c, i) => (
              <div
                key={i}
                className="flex items-center gap-2 text-xs text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded-lg px-2.5 py-1.5"
              >
                <FileText className="w-3 h-3" />
                <span className="font-bold">p.{c.page_number}</span>
                <span className="opacity-60 max-w-40 overflow-hidden text-ellipsis whitespace-nowrap">
                  {c.excerpt}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Confidence */}
        {msg.confidence && (
          <div className="flex items-center gap-2 flex-wrap">
            <ConfidenceBadge confidence={msg.confidence} />
            {msg.verified ? (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-md">
                <CheckCircle2 className="w-3 h-3" />
                KPI verified
              </span>
            ) : (
              msg.verified === false && (
                <span className="flex items-center gap-1.5 text-xs text-amber-400 bg-amber-500/10 px-2 py-1 rounded-md">
                  <AlertTriangle className="w-3 h-3" />
                  Not KPI-verified
                </span>
              )
            )}
          </div>
        )}

        {/* Suggestions */}
        {msg.suggested_questions?.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              Follow-ups
            </p>
            <div className="flex flex-wrap gap-2">
              {msg.suggested_questions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => onSuggest(q)}
                  className="text-xs text-orange-400 bg-orange-500/10 hover:bg-orange-500/20 border border-orange-500/20 hover:border-orange-500/40 rounded-lg px-3 py-1.5 transition-all cursor-pointer"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 mt-1">
          <User className="w-4 h-4 text-slate-400" />
        </div>
      )}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-orange-500/20">
        <Bot className="w-5 h-5 text-white" />
      </div>
      <div className="bg-[#0F1419]/80 backdrop-blur-md border border-white/[0.08] rounded-2xl rounded-bl-md px-5 py-3.5">
        <div className="flex gap-1.5">
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
      </div>
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [selectedFilings, setSelectedFilings] = useState([])
  const [showPicker, setShowPicker] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  const { data: companies = [] } = useQuery({
    queryKey: ['companies'],
    queryFn: () => import('../services/api').then((m) => m.getCompanies()),
  })
  const { data: allFilings = [] } = useQuery({
    queryKey: ['filings-all'],
    queryFn: () => import('../services/api').then((m) => m.getFilings()),
  })
  const completed = allFilings.filter((f) => f.status === 'completed')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const history = messages.slice(-8).map((m) => ({ role: m.role, content: m.content }))

  const askMut = useMutation({
    mutationFn: ({ question, filingIds }) => askQuestion(question, filingIds, history),
    onSuccess: (data) =>
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: data.answer,
          citations: data.citations,
          verified: data.verified_against_kpi,
          confidence: data.confidence,
          suggested_questions: data.suggested_questions || [],
        },
      ]),
    onError: (e) =>
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Error: ${e.response?.data?.detail || e.message}` },
      ]),
  })

  const send = useCallback(
    (text) => {
      const q = (text || input).trim()
      if (!q || selectedFilings.length === 0 || askMut.isPending) return
      setMessages((m) => [...m, { role: 'user', content: q }])
      setInput('')
      askMut.mutate({ question: q, filingIds: selectedFilings })
      inputRef.current?.focus()
    },
    [input, selectedFilings, askMut]
  )

  const label = (f) => {
    const c = companies.find((c) => c.id === f.company_id)
    return c ? `${c.name} FY${f.fiscal_year}` : `FY${f.fiscal_year}`
  }

  const hasActiveChat = messages.length > 0

  return (
    <div className="bg-[#08090C] relative min-h-screen overflow-hidden flex flex-col">
      {/* 3D Grid Background */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff0a_1px,transparent_1px),linear-gradient(to_bottom,#ffffff0a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none -z-10" />

      {/* Orange Glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-orange-500/10 blur-[150px] rounded-full pointer-events-none -z-10" />

      {/* Unified Top Navigation Bar */}
      <div className="w-full h-16 px-6 flex items-center justify-between border-b border-white/[0.05] bg-[#08090C]/80 backdrop-blur-md sticky top-0 z-20">
        {/* Left Side - Status with space for global hamburger */}
        <div className="flex items-center gap-3 ml-12">
          {/* Status Text */}
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex-shrink-0">
            Analyzing:
          </span>
          {selectedFilings.length === 0 ? (
            <span className="text-xs text-slate-600">No filings selected</span>
          ) : (
            <div className="flex items-center gap-2 flex-wrap">
              {selectedFilings.map((id) => {
                const f = completed.find((f) => f.id === id)
                return f ? (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded-lg px-2.5 py-1"
                  >
                    <FileText className="w-3 h-3" />
                    {label(f)}
                    <button
                      onClick={() => setSelectedFilings((s) => s.filter((x) => x !== id))}
                      className="hover:text-orange-300 transition-colors"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ) : null
              })}
            </div>
          )}
        </div>

        {/* Right Side - Select Filings Button */}
        <button
          onClick={() => setShowPicker((p) => !p)}
          className="flex items-center gap-2 px-4 py-2 bg-white/[0.05] hover:bg-white/[0.08] border border-white/10 rounded-lg text-xs font-semibold text-slate-300 transition-all flex-shrink-0"
        >
          Select filings
          <ChevronDown
            className={`w-3.5 h-3.5 transition-transform ${showPicker ? 'rotate-180' : ''}`}
          />
        </button>
      </div>

      {/* Filing Picker */}
      {showPicker && (
        <div className="w-full border-b border-white/[0.08] px-6 py-4 bg-[#0A0B0F]/90 backdrop-blur-md relative z-20 animate-in">
          {completed.length === 0 ? (
            <p className="text-sm text-slate-500">No completed filings yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {completed.map((f) => (
                <button
                  key={f.id}
                  onClick={() =>
                    setSelectedFilings((s) =>
                      s.includes(f.id) ? s.filter((x) => x !== f.id) : [...s, f.id]
                    )
                  }
                  className={`px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                    selectedFilings.includes(f.id)
                      ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30'
                      : 'bg-white/[0.05] hover:bg-white/[0.08] text-slate-400 hover:text-slate-300 border border-white/10'
                  }`}
                >
                  {label(f)}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main Chat Area - Prepared for split-screen */}
      <div className="flex-1 overflow-y-auto relative z-0">
        <div className={`${hasActiveChat ? 'w-full' : 'w-full max-w-4xl mx-auto'} h-full`}>
          {messages.length === 0 ? (
            /* Empty State */
            <div className="flex flex-col items-center justify-center h-full px-6 py-12">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-orange-500 to-orange-600 flex items-center justify-center mb-6 shadow-2xl shadow-orange-500/30">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-slate-100 text-3xl font-semibold tracking-tight mb-3">
                Chat with your reports
              </h2>
              <p className="text-sm text-slate-500 max-w-md text-center leading-relaxed mb-10">
                {completed.length > 0
                  ? 'Select one or more filings above, then ask anything about revenue, risks, or financial metrics.'
                  : 'Upload and process an annual report to begin AI-powered financial analysis.'}
              </p>

              {/* Suggestion Grid */}
              {completed.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-2xl">
                  {STARTERS.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        if (selectedFilings.length > 0) {
                          send(q)
                        } else {
                          setShowPicker(true)
                          setInput(q)
                        }
                      }}
                      className="bg-white/[0.02] backdrop-blur-md border border-white/10 p-4 rounded-xl text-left flex items-start gap-3 transition-all duration-300 hover:bg-white/[0.05] hover:border-orange-500/40 hover:shadow-[0_0_15px_rgba(255,85,0,0.1)] group cursor-pointer"
                    >
                      <Zap className="w-4 h-4 text-orange-500/70 group-hover:text-orange-400 flex-shrink-0 mt-0.5 transition-colors" />
                      <span className="text-sm text-slate-300 group-hover:text-slate-100 leading-relaxed transition-colors">
                        {q}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Messages */
            <div className="max-w-3xl mx-auto px-6 py-8 flex flex-col gap-6 pb-32">
              {messages.map((msg, i) => (
                <Message key={i} msg={msg} onSuggest={send} />
              ))}
              {askMut.isPending && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>

      {/* Floating Command Bar */}
      <div className="flex-shrink-0 pb-8 pt-4 px-6 relative z-20">
        <div className="w-full max-w-3xl mx-auto">
          {selectedFilings.length === 0 && messages.length === 0 && (
            <div className="flex items-center justify-center gap-2 mb-3 text-xs text-amber-500/80">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Select a filing above to start chatting</span>
            </div>
          )}

          <div className="relative">
            <textarea
              ref={inputRef}
              className="w-full bg-[#10121A]/80 backdrop-blur-xl border border-white/15 rounded-2xl py-4 pl-4 pr-16 text-slate-200 placeholder:text-slate-500 shadow-2xl focus:outline-none focus:border-orange-500/50 transition-colors resize-none"
              style={{ minHeight: '56px', maxHeight: '160px' }}
              placeholder={
                selectedFilings.length === 0
                  ? 'Select filings first to start asking questions...'
                  : 'Ask about revenue, risks, footnotes, management outlook...'
              }
              value={input}
              rows={1}
              onChange={(e) => {
                setInput(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
              disabled={selectedFilings.length === 0 || askMut.isPending}
            />

            {/* Send Button */}
            <button
              onClick={() => send()}
              disabled={!input.trim() || selectedFilings.length === 0 || askMut.isPending}
              className={`absolute right-2 top-2 bottom-2 aspect-square rounded-xl flex items-center justify-center transition-all ${
                input.trim() && selectedFilings.length > 0 && !askMut.isPending
                  ? 'bg-orange-600 hover:bg-orange-500 text-white shadow-lg shadow-orange-500/30 cursor-pointer'
                  : 'bg-slate-800 text-slate-600 cursor-not-allowed'
              }`}
            >
              {askMut.isPending ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>

          <p className="text-[10px] text-slate-600 text-center mt-2.5">
            Shift+Enter for new line · Enter to send
          </p>
        </div>
      </div>
    </div>
  )
}
