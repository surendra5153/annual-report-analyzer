import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2, RefreshCw, ArrowLeft, CheckCircle2, AlertTriangle, ChevronDown, ChevronUp, Zap, TrendingUp, DollarSign, Shield, Target } from 'lucide-react'
import { getDashboard, getJobByFiling, getPromises } from '../services/api'
import { StatusBadge, SeverityBadge } from '../components/StatusBadge'
import KPITable from '../components/KPITable'
import { DotLottieReact } from '@lottiefiles/dotlottie-react'

const LOTTIE_AI = 'https://lottie.host/fa6c254e-2fff-479e-9cf1-f3b93237d420/BxPqG4UKfi.lottie'

const TABS = [
  { id: 'kpis', label: 'KPIs' },
  { id: 'risks', label: 'Risks' },
  { id: 'flags', label: 'Flags' },
  { id: 'promises', label: 'Promises' },
  { id: 'sections', label: 'Summaries' },
]

const STAGE_LABELS = {
  queued: 'Queued',
  parsing: 'Parsing PDF',
  chunking: 'Chunking',
  embedding: 'Building index',
  summarizing: 'Summarizing',
  kpi_extraction: 'Extracting KPIs',
  risk_analysis: 'Classifying risks',
  footnote_check: 'Checking footnotes',
  anomaly_detect: 'Detecting anomalies',
  done: 'Complete',
}

const RISK_COLORS = {
  financial: '#f87171',
  regulatory: '#c084fc',
  cybersecurity: '#f97316',
  climate: '#34d399',
  supply_chain: '#fbbf24',
  operational: '#60a5fa',
  other: '#64748B',
}

const FLAG_LABELS = {
  inconsistency: 'Inconsistency',
  contingent_liability: 'Contingent Liability',
  related_party: 'Related Party',
  off_balance_sheet: 'Off-Balance Sheet',
  disclosure_gap: 'Disclosure Gap',
  prior_year_promise: 'Prior-Year Promise',
  anomaly: 'KPI Anomaly',
}

// Financial Summary Card Component
function FinancialCard({ label, value, icon: Icon, color = '#10b981' }) {
  return (
    <div className="bg-white/[0.02] backdrop-blur-md border border-white/10 p-5 rounded-xl hover:border-white/20 transition-all duration-300 group">
      <div className="flex justify-between items-start mb-3">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{label}</p>
        {Icon && <Icon className="w-4 h-4 text-slate-600" />}
      </div>
      <p className="text-2xl font-bold font-mono tabular-nums" style={{ color }}>
        {value}
      </p>
    </div>
  )
}

function Empty({ text }) {
  return (
    <div className="text-center py-12 text-slate-500 text-sm">
      {text}
    </div>
  )
}

function RisksTab({ risks }) {
  if (!risks?.length) return <Empty text="No risks classified yet." />
  return (
    <div className="flex flex-col gap-3">
      {risks.map((r) => (
        <div
          key={r.id}
          className="bg-[#0A0B0F]/80 backdrop-blur-md border border-white/[0.08] rounded-xl p-4 hover:border-white/20 transition-all"
        >
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ background: RISK_COLORS[r.category] || '#64748B' }}
            />
            <span className="text-sm font-semibold text-slate-100">{r.title}</span>
            <SeverityBadge severity={r.severity} />
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              {r.category?.replace('_', ' ')}
            </span>
          </div>
          <p className="text-sm text-slate-400 leading-relaxed">{r.description}</p>
          {r.page_number > 0 && (
            <p className="text-xs text-slate-600 mt-2 font-mono">p.{r.page_number}</p>
          )}
        </div>
      ))}
    </div>
  )
}

function FlagCard({ flag }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="bg-[#0A0B0F]/80 backdrop-blur-md border border-white/[0.08] rounded-xl overflow-hidden hover:border-orange-500/30 transition-all">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-white/[0.02] transition-colors"
      >
        <Zap className="w-4 h-4 text-orange-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-slate-100">{flag.title}</span>
            <SeverityBadge severity={flag.severity} />
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              {FLAG_LABELS[flag.flag_type] || flag.flag_type}
            </span>
            <span className="ml-auto text-xs text-slate-600 font-mono">
              {flag.ranking_score?.toFixed(2)}
            </span>
          </div>
          {!open && (
            <p className="text-sm text-slate-500 line-clamp-2">{flag.description}</p>
          )}
        </div>
        <div className="flex-shrink-0">
          {open ? (
            <ChevronUp className="w-4 h-4 text-slate-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-500" />
          )}
        </div>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-white/[0.08]">
          <p className="text-sm text-slate-400 leading-relaxed pt-4 mb-3">{flag.description}</p>
          {flag.footnote_text && (
            <div className="mb-3">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                Footnote
              </p>
              <blockquote className="text-sm text-slate-500 italic border-l-2 border-orange-500 pl-3 leading-relaxed">
                {flag.footnote_text}
              </blockquote>
            </div>
          )}
          {flag.narrative_text && (
            <div className="mb-3">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                Narrative
              </p>
              <blockquote className="text-sm text-slate-500 italic border-l-2 border-indigo-500 pl-3 leading-relaxed">
                {flag.narrative_text}
              </blockquote>
            </div>
          )}
          {flag.prior_year_text && (
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                Prior Year
              </p>
              <blockquote className="text-sm text-slate-500 italic border-l-2 border-purple-500 pl-3 leading-relaxed">
                {flag.prior_year_text}
              </blockquote>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FlagsTab({ flags }) {
  if (!flags?.length) return <Empty text="No flags detected." />
  return (
    <div className="flex flex-col gap-2">
      {flags.map((f) => (
        <FlagCard key={f.id} flag={f} />
      ))}
    </div>
  )
}

function PromisesTab({ filingId }) {
  const { data: promises = [], isLoading } = useQuery({
    queryKey: ['promises', filingId],
    queryFn: () => getPromises(filingId),
  })
  if (isLoading)
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="w-6 h-6 text-orange-500 animate-spin" />
      </div>
    )
  if (!promises.length)
    return <Empty text="Upload the prior year's report first, then reprocess this one." />

  const SMAP = {
    fulfilled: 'bg-emerald-500/5,text-emerald-400,border-emerald-500/20',
    partial: 'bg-amber-500/5,text-amber-400,border-amber-500/20',
    not_fulfilled: 'bg-red-500/5,text-red-400,border-red-500/20',
    not_mentioned: 'bg-slate-500/5,text-slate-400,border-slate-700/20',
  }

  return (
    <div className="flex flex-col gap-3">
      {promises.map((p) => {
        const k = p.title.split(': ')[1]?.replace(' ', '_') || 'not_mentioned'
        const classes = (SMAP[k] || SMAP.not_mentioned).split(',')
        return (
          <div
            key={p.id}
            className={`${classes[0]} border ${classes[2]} rounded-xl p-4 backdrop-blur-md`}
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <p className="text-sm font-medium text-slate-200">
                {p.prior_year_text || 'Prior-year commitment'}
              </p>
              <div className="flex gap-2 flex-shrink-0">
                <SeverityBadge severity={p.severity} />
                <span
                  className={`text-[10px] font-bold ${classes[1]} px-2 py-1 rounded uppercase tracking-wider`}
                >
                  {k.replace('_', ' ')}
                </span>
              </div>
            </div>
            {p.narrative_text && (
              <p className="text-sm text-slate-500">{p.narrative_text}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function FilingDetail() {
  const { filingId } = useParams()
  const [tab, setTab] = useState('kpis')
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['dashboard', filingId],
    queryFn: () => getDashboard(filingId),
    refetchInterval: (d) =>
      d?.filing?.status === 'processing' || d?.filing?.status === 'pending' ? 5000 : false,
  })
  const isProcessing = data?.filing?.status === 'processing' || data?.filing?.status === 'pending'
  const { data: job } = useQuery({
    queryKey: ['job', filingId],
    queryFn: () => getJobByFiling(filingId),
    refetchInterval: isProcessing ? 2000 : false,
    enabled: isProcessing,
    retry: false,
  })

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 text-orange-500 animate-spin" />
      </div>
    )

  const { filing, kpis, risks, top_flags, sections, peer_suggestions, company } = data || {}
  const verified = kpis?.filter((k) => k.is_verified).length ?? 0

  // Extract key financial metrics for the summary cards
  const getTotalRevenue = () => {
    if (!kpis || kpis.length === 0) return 'Not extracted'
    
    const revenueKPI = kpis.find(
      (k) =>
        k.name?.includes('Total Revenue') ||
        k.name?.includes('Revenue from Operations') ||
        k.metric_name?.includes('Total Revenue') ||
        k.metric_name?.includes('Revenue from Operations')
    )
    
    if (revenueKPI && revenueKPI.value != null) {
      return `₹${Number(revenueKPI.value).toLocaleString('en-IN', { maximumFractionDigits: 2 })} ${revenueKPI.unit_scale || 'Cr'}`
    }
    
    return 'Not extracted'
  }

  const getKPICount = () => {
    const count = kpis?.length || 0
    return count > 0 ? count : '—'
  }

  const getRisksCount = () => {
    const count = risks?.length || 0
    return count > 0 ? count : '—'
  }

  const getFlagsCount = () => {
    const count = top_flags?.length || 0
    return count > 0 ? count : '—'
  }

  return (
    <div className="bg-[#08090C] relative min-h-screen overflow-hidden">
      {/* 3D Grid Background */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff0a_1px,transparent_1px),linear-gradient(to_bottom,#ffffff0a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none -z-10" />

      {/* Orange Glow */}
      <div className="absolute top-0 left-1/4 w-[800px] h-[500px] bg-orange-500/10 blur-[150px] rounded-full pointer-events-none -z-10" />

      {/* Main Content */}
      <div className="relative w-full max-w-[90rem] mx-auto px-6 py-10">
        {/* Breadcrumb - Fixed with pl-16 */}
        {filing?.company_id && (
          <div className="pl-16 mb-8">
            <Link
              to={`/companies/${filing.company_id}`}
              className="inline-flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-orange-500 transition-colors uppercase tracking-wider"
            >
              <ArrowLeft className="w-3 h-3" />
              Back to Company
            </Link>
          </div>
        )}

        {/* Header - Fixed hierarchy */}
        <div className="flex items-start justify-between mb-8 pl-16">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold text-slate-100 tracking-tight">
                {company?.name || 'Company Name'}
              </h1>
              <span className="text-sm font-bold text-orange-500 bg-orange-500/10 px-3 py-1.5 rounded-lg border border-orange-500/20 shadow-[0_0_15px_rgba(255,85,0,0.15)]">
                FY {filing?.fiscal_year}
              </span>
            </div>
            <p className="text-sm text-slate-400">
              {filing?.file_name}
              {filing?.page_count && ` • ${filing.page_count} pages`}
              {` • ${filing?.currency} ${filing?.unit_scale}`}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <StatusBadge status={filing?.status} />
            <button
              className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.05] hover:bg-white/[0.08] border border-white/10 rounded-lg text-xs font-semibold text-slate-300 transition-all"
              onClick={() => refetch()}
            >
              <RefreshCw
                className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`}
              />
              Refresh
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        {isProcessing && (
          <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-4 mb-8 flex items-center gap-4 pl-16 backdrop-blur-md">
            <div className="w-12 h-12 flex-shrink-0">
              <DotLottieReact
                src={LOTTIE_AI}
                autoplay
                loop
                style={{ width: '100%', height: '100%' }}
              />
            </div>
            <div className="flex-1">
              {job && job.status !== 'failed' ? (
                <div>
                  <div className="flex justify-between text-sm text-indigo-400 mb-2 font-semibold">
                    <span>{STAGE_LABELS[job.stage] || job.stage}…</span>
                    <span className="font-mono">{job.progress_pct}%</span>
                  </div>
                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{ width: `${job.progress_pct}%`, background: '#818cf8' }}
                    />
                  </div>
                </div>
              ) : (
                <p className="text-sm text-indigo-400">Processing your report…</p>
              )}
            </div>
          </div>
        )}

        {/* Error State */}
        {filing?.status === 'failed' && (
          <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-4 mb-8 pl-16 backdrop-blur-md">
            <p className="text-sm font-semibold text-red-400 mb-1">Processing failed</p>
            {filing.error_message && (
              <p className="text-sm text-red-400/70 font-mono">{filing.error_message}</p>
            )}
          </div>
        )}

        {/* Similar Companies - Spread horizontally */}
        {peer_suggestions?.length > 0 && (
          <div className="mb-8 pl-16">
            <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">
              Similar Companies
            </h2>
            <div className="flex flex-wrap gap-3">
              {peer_suggestions.map((p) => (
                <span
                  key={p.company_id}
                  className="text-xs font-semibold text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded-lg px-3 py-2 hover:bg-indigo-500/20 transition-colors cursor-pointer"
                >
                  {p.name}
                  {p.ticker && (
                    <span className="font-mono ml-2 opacity-60">{p.ticker}</span>
                  )}
                  <span className="opacity-50 ml-2">{(p.score * 100).toFixed(0)}%</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Financial Summary Cards */}
        <div className="grid grid-cols-4 gap-4 mb-8 pl-16">
          <FinancialCard
            label="KPIs Extracted"
            value={getKPICount()}
            icon={Target}
            color="#818cf8"
          />
          <FinancialCard
            label="Risks Identified"
            value={getRisksCount()}
            icon={AlertTriangle}
            color="#f87171"
          />
          <FinancialCard
            label="Flags Detected"
            value={getFlagsCount()}
            icon={Zap}
            color="#fbbf24"
          />
          <FinancialCard
            label="Total Revenue"
            value={getTotalRevenue()}
            icon={DollarSign}
            color="#10b981"
          />
        </div>

        {/* Tabs - Full width */}
        <div className="flex gap-1 border-b border-white/[0.08] mb-8 pl-16 overflow-x-auto">
          {TABS.map(({ id, label }) => {
            const active = tab === id
            const counts = {
              kpis: kpis?.length,
              risks: risks?.length,
              flags: top_flags?.length,
              sections: sections?.length,
            }
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`px-6 py-3 text-xs font-bold uppercase tracking-wider transition-all whitespace-nowrap ${
                  active
                    ? 'text-slate-100 border-b-2 border-orange-500'
                    : 'text-slate-500 border-b-2 border-transparent hover:text-slate-300'
                }`}
                style={{ marginBottom: '-1px' }}
              >
                <span className="flex items-center gap-2">
                  {label}
                  {counts[id] > 0 && (
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded ${
                        active
                          ? 'bg-orange-500/10 text-orange-500'
                          : 'bg-white/[0.05] text-slate-600'
                      }`}
                    >
                      {counts[id]}
                    </span>
                  )}
                </span>
              </button>
            )
          })}
        </div>

        {/* Content */}
        <div className="animate-in pl-16">
          {tab === 'kpis' && <KPITable kpis={kpis} />}
          {tab === 'risks' && <RisksTab risks={risks} />}
          {tab === 'flags' && <FlagsTab flags={top_flags} />}
          {tab === 'promises' && <PromisesTab filingId={filingId} />}
          {tab === 'sections' && (
            <div className="flex flex-col gap-6">
              {sections?.length ? (
                sections.map((s) => (
                  <div
                    key={s.id}
                    className="border-b border-white/[0.08] pb-6 last:border-0"
                  >
                    <div className="flex items-center gap-2 mb-3">
                      <h3 className="text-sm font-bold text-slate-100 capitalize">
                        {s.section_name.replace(/_/g, ' ')}
                      </h3>
                      {s.start_page && (
                        <span className="text-xs text-slate-600 font-mono">
                          pp.{s.start_page}–{s.end_page}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-400 leading-relaxed whitespace-pre-wrap">
                      {s.summary}
                    </p>
                  </div>
                ))
              ) : (
                <Empty text="No summaries yet." />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
