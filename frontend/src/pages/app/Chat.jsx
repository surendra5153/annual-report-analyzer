import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, FileText, X } from 'lucide-react'
import { filingPdfUrl, getCompanies, getFilings } from '@/services/api'
import ChatPanel from '@/components/app/ChatPanel'
import PdfViewer from '@/components/app/PdfViewer'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/misc'
import { cn, shortCompany } from '@/lib/utils'

export default function Chat() {
  const { data: companies = [] } = useQuery({ queryKey: ['companies'], queryFn: getCompanies })
  const { data: filings = [], isLoading } = useQuery({ queryKey: ['filings-all'], queryFn: () => getFilings() })
  const [selected, setSelected] = useState([])
  const [doc, setDoc] = useState(null) // { filingId, page, text, nonce }

  const ready = filings.filter((f) => f.status === 'completed')
  const companyName = useMemo(() => Object.fromEntries(companies.map((c) => [c.id, c.name])), [companies])
  const grouped = useMemo(() => {
    const g = {}
    for (const f of ready) (g[f.company_id] ||= []).push(f)
    return Object.entries(g).map(([cid, fs]) => [cid, fs.sort((a, b) => b.fiscal_year - a.fiscal_year)])
  }, [ready])

  // Default: most recent report selected
  useEffect(() => {
    if (!selected.length && ready.length) {
      setSelected([[...ready].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0].id])
    }
  }, [ready.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  const label = (f) => `${shortCompany(companyName[f.company_id] || f.file_name)} FY${f.fiscal_year}`

  return (
    <div className="flex h-[calc(100vh-56px)] min-h-0">
      <aside className="hidden w-[260px] shrink-0 flex-col border-r bg-background md:flex">
        <div className="border-b px-4 py-3">
          <p className="text-[13px] font-semibold">Reports in scope</p>
          <p className="text-[12px] text-muted-foreground">{selected.length} selected · answers cite these</p>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-3">
          {isLoading && <Skeleton className="h-40" />}
          {grouped.map(([cid, fs]) => (
            <div key={cid}>
              <p className="mb-1 truncate px-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {shortCompany(companyName[cid] || '')}
              </p>
              {fs.map((f) => {
                const on = selected.includes(f.id)
                return (
                  <button key={f.id} onClick={() => toggle(f.id)}
                    className={cn('flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-[13px] transition-colors hover:bg-accent', on && 'bg-accent')}>
                    <span className={cn('grid size-4 shrink-0 place-items-center rounded border', on && 'border-primary bg-primary text-primary-foreground')}>
                      {on && <Check className="size-3" />}
                    </span>
                    <span className="flex-1">FY{f.fiscal_year}</span>
                    <span className="text-[11px] text-muted-foreground">{f.page_count}p</span>
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 overflow-x-auto border-b bg-background px-4 py-2.5 md:hidden">
          {ready.map((f) => (
            <button key={f.id} onClick={() => toggle(f.id)}
              className={cn('shrink-0 rounded-full border px-2.5 py-1 text-[12px]', selected.includes(f.id) ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground')}>
              {label(f)}
            </button>
          ))}
        </div>
        <div className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col px-4 py-4">
          {selected.length > 1 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {selected.map((id) => {
                const f = ready.find((x) => x.id === id)
                return f && (
                  <span key={id} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-[12px]">
                    {label(f)}
                    <button onClick={() => toggle(id)} aria-label="Remove"><X className="size-3" /></button>
                  </span>
                )
              })}
            </div>
          )}
          <ChatPanel
            key={selected.join(',')}
            filingIds={selected}
            onCite={(s) => setDoc({ filingId: s.filing_id, page: s.page_number, text: s.kind === 'kpi_table' ? null : s.excerpt, nonce: Date.now() })}
            className="min-h-0 flex-1"
            emptyTitle={selected.length > 1 ? `Ask across ${selected.length} reports` : 'Ask anything about the selected report'}
            suggestions={selected.length > 1
              ? ['Compare total revenue across these reports.', 'Which company reports higher debt?', 'How do their key risks differ?']
              : undefined}
          />
        </div>
      </section>

      <AnimatePresence>
        {doc && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }} animate={{ width: '42%', opacity: 1 }} exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="hidden min-w-0 shrink-0 flex-col overflow-hidden border-l lg:flex"
          >
            <div className="flex h-11 items-center gap-2 border-b bg-background px-3">
              <FileText className="size-4 text-muted-foreground" />
              <span className="truncate text-[13px] font-medium">
                {(() => { const f = filings.find((x) => x.id === doc.filingId); return f ? label(f) : 'Source' })()}
              </span>
              <Button variant="ghost" size="icon-sm" className="ml-auto" onClick={() => setDoc(null)} aria-label="Close"><X /></Button>
            </div>
            <PdfViewer key={doc.filingId} url={filingPdfUrl(doc.filingId)} target={doc} className="min-h-0 flex-1"
              onClearHighlight={() => setDoc((d) => ({ ...d, text: null }))} />
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  )
}
