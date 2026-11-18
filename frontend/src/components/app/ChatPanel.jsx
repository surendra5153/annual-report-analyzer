import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { motion } from 'framer-motion'
import { ArrowUp, FileText, RotateCcw, Sparkles, Square, Table2, Landmark } from 'lucide-react'
import { streamQuestion } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/input'
import { Tooltip } from '@/components/ui/tooltip'
import { addCroreEquivalents, cn } from '@/lib/utils'

const CITE_RE = /\[(?:sources?\s*)?(\d{1,2}(?:\s*(?:,|and|&)\s*\d{1,2})*)(?:\s*\|[^\]]*)?\]/gi

/** Turn "[Source 3]" / "[1, 2]" into markdown links (#cite-n) rendered as chips. */
function linkCitations(text) {
  return text
    .replace(CITE_RE, (_, group) => group.match(/\d+/g).map((n) => `[${n}](#cite-${n})`).join(' '))
    // bare "Source 1" (no brackets) — keep the word, link the number
    .replace(/(?<!\[)\bSource\s+(\d{1,2})\b/g, (_, n) => `Source [${n}](#cite-${n})`)
}

const CONFIDENCE = { high: 'success', medium: 'warning', low: 'danger' }

const DEFAULT_SUGGESTIONS = [
  'What was the total revenue and how did it change?',
  'Summarise the key risks the company highlights.',
  'Who are the statutory auditors?',
  'What is the dividend recommended for the year?',
]

function Message({ msg, onCite }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-[13.5px] text-primary-foreground">
          {msg.content}
        </div>
      </div>
    )
  }

  const sources = msg.sources || []
  const cited = new Set(msg.cited || [])
  const shown = cited.size ? sources.filter((s) => cited.has(s.index)) : []

  return (
    <div className="flex gap-3">
      <div className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
        <Sparkles className="size-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        {msg.error ? (
          <p className="text-[13.5px] text-danger">{msg.error}</p>
        ) : !msg.content && msg.streaming ? (
          <div className="flex items-center gap-2 py-1.5 text-[13px] text-muted-foreground">
            <span className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <motion.span key={i} className="size-1.5 rounded-full bg-muted-foreground"
                  animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }} />
              ))}
            </span>
            {sources.length ? `Reading ${sources.length} passages…` : 'Searching the report…'}
          </div>
        ) : (
          <div className="prose-sm-app text-[13.5px] text-foreground/90">
            <ReactMarkdown
              components={{
                a: ({ href, children }) => {
                  const n = Number(href?.replace('#cite-', ''))
                  const src = sources.find((s) => s.index === n)
                  if (!src) return <span>{children}</span>
                  return (
                    <Tooltip content={src.kind === 'kpi_table' ? 'Verified KPI table (extracted from the financial statements)' : `p.${src.page_number} — ${src.excerpt.slice(0, 140)}…`}>
                      <button
                        onClick={() => onCite?.(src)}
                        className="mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md bg-primary/10 px-1 align-middle text-[10.5px] font-semibold text-primary hover:bg-primary hover:text-primary-foreground"
                      >
                        {n}
                      </button>
                    </Tooltip>
                  )
                },
              }}
            >
              {linkCitations(addCroreEquivalents(msg.content))}
            </ReactMarkdown>
            {msg.streaming && <span className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-blink bg-foreground" />}
          </div>
        )}

        {!msg.streaming && !msg.error && (
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            {msg.mode === 'table_reader' ? (
              <Tooltip content="Read directly from the financial-statement table and computed in code — no language model involved">
                <Badge variant="success"><Landmark /> Read from statement · exact</Badge>
              </Tooltip>
            ) : msg.confidence && (
              <Badge variant={CONFIDENCE[msg.confidence]} className="capitalize">{msg.confidence} confidence</Badge>
            )}
            {shown.map((s) => (
              <button
                key={s.index}
                onClick={() => onCite?.(s)}
                className="inline-flex items-center gap-1 rounded-md border bg-background px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {s.kind === 'kpi_table'
                  ? <><Table2 className="size-3 text-primary" /> [{s.index}] KPI table</>
                  : s.kind === 'statement_page'
                    ? <><Landmark className="size-3 text-primary" /> [{s.index}] Statement p.{s.page_number}</>
                    : <><FileText className="size-3" /> [{s.index}] p.{s.page_number}</>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Streaming RAG chat. `filingIds` scopes retrieval; `onCite(source)` is called
 * when a citation chip is clicked (the workspace opens the PDF there).
 */
export default function ChatPanel({ filingIds, onCite, className, placeholder, suggestions = DEFAULT_SUGGESTIONS, emptyTitle }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const abortRef = useRef(null)
  const endRef = useRef(null)
  const busy = messages.some((m) => m.streaming)

  // Block body: scrollIntoView() returns a Promise in recent Chrome, which must not become the effect's cleanup
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])
  useEffect(() => () => abortRef.current?.(), [])

  const update = (id, fn) => setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...fn(m) } : m)))

  const ask = (question) => {
    const q = question.trim()
    if (!q || busy || !filingIds?.length) return
    const history = messages.filter((m) => !m.error).map((m) => ({ role: m.role, content: m.content })).slice(-8)
    const id = crypto.randomUUID()
    setMessages((ms) => [...ms, { id: `${id}-q`, role: 'user', content: q }, { id, role: 'assistant', content: '', streaming: true }])
    setInput('')
    abortRef.current = streamQuestion({
      question: q,
      filingIds,
      conversationHistory: history,
      onEvent: (e) => {
        if (e.type === 'sources') update(id, () => ({ sources: e.sources }))
        else if (e.type === 'token') update(id, (m) => ({ content: m.content + e.text }))
        else if (e.type === 'done') update(id, () => ({ streaming: false, confidence: e.confidence, cited: e.cited, mode: e.mode }))
        else if (e.type === 'error') update(id, () => ({ streaming: false, error: e.message }))
      },
    })
  }

  const stop = () => {
    abortRef.current?.()
    setMessages((ms) => ms.map((m) => (m.streaming ? { ...m, streaming: false } : m)))
  }

  return (
    <div className={cn('flex min-h-0 flex-col', className)}>
      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-1 py-2">
        {messages.length === 0 ? (
          <div className="mx-auto flex h-full max-w-md flex-col items-center justify-center py-8 text-center">
            <div className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
              <Sparkles className="size-5" />
            </div>
            <p className="mt-3 font-medium">{emptyTitle || 'Ask anything about this report'}</p>
            <p className="mt-1 text-[13px] text-muted-foreground">
              Answers are grounded in the report text, cite their sources, and are generated by a local model.
            </p>
            <div className="mt-5 grid w-full gap-2">
              {suggestions.map((s) => (
                <button key={s} onClick={() => ask(s)} disabled={!filingIds?.length}
                  className="rounded-lg border bg-background px-3 py-2 text-left text-[13px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-50">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <Message key={m.id} msg={m} onCite={onCite} />)
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); ask(input) }}
        className="relative mt-3 rounded-xl border bg-background shadow-sm focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30"
      >
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input) } }}
          placeholder={filingIds?.length ? placeholder || 'Ask a question… (Enter to send)' : 'Select at least one report first'}
          disabled={!filingIds?.length}
          rows={2}
          className="border-0 bg-transparent pr-24 shadow-none focus-visible:ring-0"
        />
        <div className="absolute bottom-2 right-2 flex items-center gap-1">
          {messages.length > 0 && !busy && (
            <Tooltip content="New conversation">
              <Button type="button" variant="ghost" size="icon-sm" onClick={() => setMessages([])}><RotateCcw /></Button>
            </Tooltip>
          )}
          {busy ? (
            <Button type="button" size="icon-sm" variant="secondary" onClick={stop} aria-label="Stop"><Square className="fill-current" /></Button>
          ) : (
            <Button type="submit" size="icon-sm" disabled={!input.trim() || !filingIds?.length} aria-label="Send"><ArrowUp /></Button>
          )}
        </div>
      </form>
    </div>
  )
}
