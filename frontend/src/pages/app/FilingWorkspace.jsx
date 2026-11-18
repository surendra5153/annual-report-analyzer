import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { toast } from 'sonner'
import {
  AlertTriangle, Ban, BookOpenText, Check, ChevronRight, CircleCheck, FileSearch, FileText, Gauge, Handshake,
  MessagesSquare, MoreHorizontal, PanelRightClose, PanelRightOpen, ShieldAlert, Trash2,
} from 'lucide-react'
import { deleteFiling, filingPdfUrl, getDashboard, getJobByFiling, getPromises } from '@/services/api'
import { StatusBadge } from '@/components/app/domain'
import PdfViewer from '@/components/app/PdfViewer'
import ChatPanel from '@/components/app/ChatPanel'
import { Button } from '@/components/ui/button'
import { Badge, SeverityBadge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Tabs, TabsContent, TabsListLine, TabsTriggerLine } from '@/components/ui/tabs'
import { EmptyState, Progress, Skeleton } from '@/components/ui/misc'
import { Input } from '@/components/ui/input'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { Tooltip } from '@/components/ui/tooltip'
import { cn, formatKPI, titleCase } from '@/lib/utils'

const STAGES = [
  ['parsing', 'Parse PDF'], ['chunking', 'Chunk'], ['embedding', 'Index'], ['summarizing', 'Summarise'],
  ['kpi_extraction', 'Extract KPIs'], ['risk_analysis', 'Risks'], ['footnote_check', 'Footnotes'], ['anomaly_detect', 'Anomalies'],
]

const SECTION_TITLES = {
  business_overview: 'Business overview', financial_highlights: 'Financial highlights', mda: 'Management discussion & analysis',
  risk_factors: 'Risk factors', outlook: 'Outlook', footnotes: 'Notes & footnotes',
}

function PipelineStepper({ job }) {
  const idx = STAGES.findIndex(([s]) => s === job?.stage)
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="font-medium">Analysing on local models…</p>
          <p className="text-[13px] text-muted-foreground">This page updates live. Large reports take a few minutes.</p>
        </div>
        <span className="tabular text-[13px] font-medium">{job?.progress_pct ?? 0}%</span>
      </div>
      <Progress value={job?.progress_pct ?? 2} />
      <ol className="mt-5 grid grid-cols-4 gap-3 sm:grid-cols-8">
        {STAGES.map(([key, label], i) => {
          const done = idx > i || job?.status === 'done'
          const active = idx === i
          return (
            <li key={key} className="flex flex-col items-center gap-1.5 text-center">
              <span className={cn('grid size-7 place-items-center rounded-full border text-[11px] font-medium transition-colors',
                done && 'border-primary bg-primary text-primary-foreground',
                active && 'border-primary text-primary ring-4 ring-primary/15')}>
                {done ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span className={cn('text-[11px] text-muted-foreground', active && 'font-medium text-foreground')}>{label}</span>
            </li>
          )
        })}
      </ol>
    </Card>
  )
}

function PageLink({ page, onClick }) {
  if (!page) return null
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary">
      <FileSearch className="size-3" /> p.{page}
    </button>
  )
}

function KpiTab({ kpis, unitScale, onOpen }) {
  const [q, setQ] = useState('')
  const groups = useMemo(() => {
    const g = {}
    for (const k of kpis.filter((k) => k.name.toLowerCase().includes(q.toLowerCase()))) (g[k.category || 'Other'] ||= []).push(k)
    return Object.entries(g)
  }, [kpis, q])
  const verified = kpis.filter((k) => k.is_verified).length
  const rejected = kpis.filter((k) => k.value === null).length
  const source = kpis.find((k) => k.source_unit)?.source_unit

  if (!kpis.length) return <EmptyState icon={Gauge} title="No KPIs extracted" description="The extractor found no recognisable financial line items." />
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter KPIs…" className="h-8 max-w-[240px]" />
        <p className="text-[12.5px] text-muted-foreground">
          {kpis.length} KPIs · <span className="text-success">{verified} verified</span>
          {rejected > 0 && <> · <span className="text-danger">{rejected} rejected by consistency rules</span></>}
          {source ? ` · normalised to ₹ crore (report states ₹ ${source})` : ` · values as reported (₹ ${unitScale})`}
        </p>
      </div>
      {groups.map(([cat, items]) => (
        <Card key={cat} className="overflow-hidden">
          <div className="border-b bg-muted/40 px-4 py-2 text-[12px] font-medium text-muted-foreground">{cat}</div>
          <table className="w-full text-[13px]">
            <tbody>
              {items.map((k) => (
                <tr key={k.id} className="group border-b last:border-0 hover:bg-accent/40">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{k.name}</span>
                      {k.value === null ? (
                        <Tooltip content={k.verification_note || 'Rejected by consistency rules'}>
                          <Badge variant="danger"><Ban /> rejected</Badge>
                        </Tooltip>
                      ) : k.is_verified && (
                        <Tooltip content={k.verification_note || 'Passed cross-KPI verification'}>
                          <CircleCheck className="size-3.5 text-success" />
                        </Tooltip>
                      )}
                    </div>
                    {k.source_text && <p className="mt-0.5 line-clamp-1 font-mono text-[11px] text-muted-foreground">{k.source_text}</p>}
                  </td>
                  <td className="tabular whitespace-nowrap px-3 py-2.5 text-right">
                    {k.value === null ? (
                      <span className="text-muted-foreground line-through decoration-danger/60">{formatKPI(k.raw_value, null, unitScale, k.name)}</span>
                    ) : (
                      <Tooltip content={k.raw_value != null && k.raw_value !== k.value ? `As printed: ${formatKPI(k.raw_value, null, k.source_unit ? k.source_unit + 's' : unitScale, k.name)}` : null}>
                        <span className="font-medium">{formatKPI(k.value, k.unit, unitScale, k.name)}</span>
                      </Tooltip>
                    )}
                  </td>
                  <td className="w-16 px-3 py-2.5 text-right">
                    <PageLink page={k.page_number} onClick={() => onOpen(k.page_number, k.source_text)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  )
}

function RiskTab({ risks, onOpen }) {
  const [cat, setCat] = useState('all')
  const cats = ['all', ...new Set(risks.map((r) => r.category))]
  const list = risks.filter((r) => cat === 'all' || r.category === cat)
  if (!risks.length) return <EmptyState icon={ShieldAlert} title="No risks identified" />
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {cats.map((c) => (
          <button key={c} onClick={() => setCat(c)}
            className={cn('rounded-full border px-2.5 py-1 text-[12px] transition-colors', cat === c ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground')}>
            {titleCase(c)} {c !== 'all' && <span className="opacity-60">{risks.filter((r) => r.category === c).length}</span>}
          </button>
        ))}
      </div>
      {list.map((r) => (
        <Card key={r.id} className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-medium">{r.title}</p>
              <p className="mt-0.5 text-[12px] text-muted-foreground">{titleCase(r.category)}</p>
            </div>
            <div className="flex items-center gap-1">
              <PageLink page={r.page_number} onClick={() => onOpen(r.page_number, r.source_text)} />
              <SeverityBadge severity={r.severity} />
            </div>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{r.description}</p>
        </Card>
      ))}
    </div>
  )
}

function FlagTab({ flags, empty, onOpen }) {
  if (!flags.length) return <EmptyState icon={AlertTriangle} title={empty} />
  return (
    <div className="space-y-3">
      {flags.map((f) => (
        <Card key={f.id} className="p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-medium">{f.title}</p>
              <p className="mt-0.5 text-[12px] text-muted-foreground">{titleCase(f.flag_type)}</p>
            </div>
            <div className="flex items-center gap-1">
              <PageLink page={f.page_number} onClick={() => onOpen(f.page_number, f.footnote_text || f.narrative_text)} />
              <SeverityBadge severity={f.severity} />
            </div>
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{f.description}</p>
          {(f.narrative_text || f.footnote_text || f.prior_year_text) && (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {[['Narrative says', f.narrative_text], ['Footnote says', f.footnote_text], ['Prior year said', f.prior_year_text]]
                .filter(([, t]) => t)
                .map(([label, t]) => (
                  <div key={label} className="rounded-md border bg-muted/40 p-2.5">
                    <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
                    <p className="line-clamp-4 text-[12px] leading-relaxed">{t}</p>
                  </div>
                ))}
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}

function SummaryTab({ sections, peers, onOpen }) {
  if (!sections.length) return <EmptyState icon={BookOpenText} title="No summaries yet" />
  return (
    <div className="space-y-3">
      {sections.map((s) => (
        <Card key={s.id} className="p-5">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h3 className="font-semibold">{SECTION_TITLES[s.section_name] || titleCase(s.section_name)}</h3>
            {s.start_page && (
              <PageLink page={s.start_page} onClick={() => onOpen(s.start_page, null)} />
            )}
          </div>
          <div className="prose-sm-app text-[13.5px] text-muted-foreground">
            <ReactMarkdown>{s.summary || '_No summary._'}</ReactMarkdown>
          </div>
        </Card>
      ))}
      {peers?.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-3 font-semibold">Similar companies</h3>
          <div className="flex flex-wrap gap-2">
            {peers.map((p) => (
              <Badge key={p.company_id || p.company_name} variant="outline" className="px-2 py-1 text-[12px]">
                {p.company_name}
                {p.similarity_score != null && <span className="text-primary">{Math.round(p.similarity_score * 100)}%</span>}
              </Badge>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}

export default function FilingWorkspace() {
  const { filingId } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'summary'
  const [pdfOpen, setPdfOpen] = useState(true)
  const [target, setTarget] = useState(null)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard', filingId],
    queryFn: () => getDashboard(filingId),
    refetchInterval: (q) => (['processing', 'pending'].includes(q.state.data?.filing?.status) ? 3000 : false),
  })
  const status = data?.filing?.status
  const processing = status === 'processing' || status === 'pending'
  const { data: job } = useQuery({
    queryKey: ['job', filingId],
    queryFn: () => getJobByFiling(filingId),
    enabled: processing,
    refetchInterval: processing ? 2000 : false,
  })
  const { data: promises = [] } = useQuery({
    queryKey: ['promises', filingId],
    queryFn: () => getPromises(filingId),
    enabled: status === 'completed',
  })

  const del = useMutation({
    mutationFn: () => deleteFiling(filingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['filings-all'] })
      toast.success('Report deleted')
      navigate('/app')
    },
  })

  const open = (page, text) => {
    setPdfOpen(true)
    setTarget({ page, text: text || null, nonce: Date.now() })
  }

  if (isLoading) {
    return (
      <div className="grid h-[calc(100vh-56px)] lg:grid-cols-2">
        <div className="space-y-4 p-6"><Skeleton className="h-8 w-72" /><Skeleton className="h-10" /><Skeleton className="h-64" /></div>
        <Skeleton className="hidden rounded-none lg:block" />
      </div>
    )
  }
  if (isError || !data) {
    return <div className="p-8"><EmptyState icon={FileText} title="Report not found" action={<Button asChild variant="outline"><Link to="/app">Back to overview</Link></Button>} /></div>
  }

  const { filing, company, kpis, risks, top_flags: flags, sections, peer_suggestions: peers } = data
  const setTab = (t) => setParams((p) => { p.set('tab', t); return p }, { replace: true })

  const tabs = [
    ['summary', 'Summary', BookOpenText, sections.length],
    ['kpis', 'KPIs', Gauge, kpis.length],
    ['risks', 'Risks', ShieldAlert, risks.length],
    ['footnotes', 'Footnotes', AlertTriangle, flags.length],
    ['promises', 'Promises', Handshake, promises.length],
    ['chat', 'Ask AI', MessagesSquare],
  ]

  return (
    <div className="flex h-[calc(100vh-56px)] min-h-0">
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="border-b bg-background px-4 pt-4 lg:px-6">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="mb-1 flex items-center gap-1 text-[12px] text-muted-foreground">
                <Link to="/app/companies" className="hover:text-foreground">Companies</Link>
                <ChevronRight className="size-3" />
                <Link to={`/app/companies/${company.id}`} className="truncate hover:text-foreground">{company.name}</Link>
              </div>
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="truncate text-xl font-semibold tracking-tight">Annual Report FY{filing.fiscal_year}</h1>
                <StatusBadge status={filing.status} />
              </div>
              <p className="mt-1 text-[12.5px] text-muted-foreground">
                {filing.file_name} · {filing.page_count ?? '—'} pages · {filing.currency} {filing.unit_scale}
                {company.sector ? ` · ${company.sector}` : ''}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <Tooltip content={pdfOpen ? 'Hide PDF' : 'Show PDF'}>
                <Button variant="outline" size="icon-sm" onClick={() => setPdfOpen((o) => !o)} className="hidden lg:inline-flex">
                  {pdfOpen ? <PanelRightClose /> : <PanelRightOpen />}
                </Button>
              </Tooltip>
              <DropdownMenu>
                <DropdownMenuTrigger asChild><Button variant="ghost" size="icon-sm"><MoreHorizontal /></Button></DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem asChild><a href={filingPdfUrl(filing.id)} target="_blank" rel="noreferrer"><FileText /> Open original PDF</a></DropdownMenuItem>
                  <DropdownMenuItem className="text-danger focus:text-danger" onSelect={() => { if (window.confirm('Delete this report and all its analysis?')) del.mutate() }}>
                    <Trash2 className="!text-danger" /> Delete report
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          <Tabs value={tab} onValueChange={setTab}>
            <TabsListLine className="mt-4 border-0">
              {tabs.map(([v, label, Icon, count]) => (
                <TabsTriggerLine key={v} value={v} disabled={processing && v !== 'summary'}>
                  <Icon /> {label}
                  {count > 0 && <span className="tabular rounded bg-muted px-1 text-[10.5px] text-muted-foreground">{count}</span>}
                </TabsTriggerLine>
              ))}
            </TabsListLine>
          </Tabs>
        </div>

        <div className={cn('min-h-0 flex-1 px-4 py-5 lg:px-6', tab === 'chat' ? 'flex flex-col' : 'overflow-y-auto')}>
          {processing ? (
            <PipelineStepper job={job} />
          ) : (
            <Tabs value={tab} onValueChange={setTab} className={cn(tab === 'chat' && 'flex min-h-0 flex-1 flex-col')}>
              <TabsContent value="summary" className="mt-0"><SummaryTab sections={sections} peers={peers} onOpen={open} /></TabsContent>
              <TabsContent value="kpis" className="mt-0"><KpiTab kpis={kpis} unitScale={filing.unit_scale} onOpen={open} /></TabsContent>
              <TabsContent value="risks" className="mt-0"><RiskTab risks={risks} onOpen={open} /></TabsContent>
              <TabsContent value="footnotes" className="mt-0"><FlagTab flags={flags} empty="No footnote inconsistencies found" onOpen={open} /></TabsContent>
              <TabsContent value="promises" className="mt-0"><FlagTab flags={promises} empty="No prior-year promises tracked" onOpen={open} /></TabsContent>
              <TabsContent value="chat" className="mt-0 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden" forceMount>
                <ChatPanel filingIds={[filing.id]} onCite={(s) => open(s.page_number, s.kind === 'kpi_table' ? null : s.excerpt)} className="min-h-0 flex-1" />
              </TabsContent>
            </Tabs>
          )}
        </div>
      </section>

      {pdfOpen && (
        <aside className="hidden w-[46%] max-w-[760px] shrink-0 border-l lg:block">
          <PdfViewer url={filingPdfUrl(filing.id)} target={target} onClearHighlight={() => setTarget((t) => t && { ...t, text: null })} />
        </aside>
      )}
    </div>
  )
}
