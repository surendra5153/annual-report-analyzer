import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowUpRight, Building2, ChevronRight, FileText, MessagesSquare, Star, Trash2, Upload } from 'lucide-react'
import { deleteCompany, getCompanyProfile, updateCompany } from '@/services/api'
import { PageBody, PageHeader } from '@/components/app/AppShell'
import { axisProps, CHART, ChartTooltip, gridProps, StatTile, StatusBadge } from '@/components/app/domain'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/input'
import { Delta, EmptyState, Skeleton } from '@/components/ui/misc'
import { formatKPI, formatNumber, pctChange } from '@/lib/utils'

const HEADLINE = [
  ['Total Revenue', 'Revenue'],
  ['Profit After Tax (PAT) / Net Profit', 'Net profit'],
  ['Total Assets', 'Total assets'],
  ['Earnings Per Share (EPS)', 'EPS'],
]

export default function CompanyProfile() {
  const { companyId } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data, isLoading, isError } = useQuery({ queryKey: ['company-profile', companyId], queryFn: () => getCompanyProfile(companyId) })
  const [metric, setMetric] = useState(null)

  const track = useMutation({
    mutationFn: () => updateCompany(companyId, { ...data.company, is_tracked: !data.company.is_tracked }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['company-profile', companyId] }); qc.invalidateQueries({ queryKey: ['companies'] }) },
  })
  const remove = useMutation({
    mutationFn: () => deleteCompany(companyId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['companies'] }); toast.success('Company removed'); navigate('/app/companies') },
    onError: (e) => toast.error(e.response?.data?.detail || 'Delete failed'),
  })

  const trends = data?.kpi_trends || {}
  const metrics = useMemo(() => Object.keys(trends).filter((k) => trends[k].length).sort(), [trends])
  const active = metric || (metrics.includes('Total Revenue') ? 'Total Revenue' : metrics[0])

  const series = useMemo(() => {
    const byYear = {}
    for (const p of trends[active] || []) byYear[p.fiscal_year] = p
    return Object.values(byYear).sort((a, b) => a.fiscal_year - b.fiscal_year).map((p) => ({ year: `FY${p.fiscal_year}`, value: p.value, unit: p.unit_scale }))
  }, [trends, active])

  if (isLoading) return <PageBody><Skeleton className="h-8 w-80" /><div className="grid gap-4 sm:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div><Skeleton className="h-80" /></PageBody>
  if (isError || !data) return <PageBody><EmptyState icon={Building2} title="Company not found" /></PageBody>

  const { company, filings, peers } = data
  const done = filings.filter((f) => f.status === 'completed')
  const latest = (name) => {
    const pts = [...(trends[name] || [])].sort((a, b) => b.fiscal_year - a.fiscal_year)
    return { now: pts[0], prev: pts[1] }
  }

  return (
    <PageBody>
      <div className="flex items-center gap-1 text-[12px] text-muted-foreground">
        <Link to="/app/companies" className="hover:text-foreground">Companies</Link>
        <ChevronRight className="size-3" />
        <span className="text-foreground">{company.name}</span>
      </div>
      <PageHeader
        title={company.name}
        description={[company.ticker, company.sector, company.industry].filter(Boolean).join(' · ') || 'Company profile'}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => track.mutate()}>
              <Star className={company.is_tracked ? 'fill-warning text-warning' : ''} /> {company.is_tracked ? 'Tracked' : 'Track'}
            </Button>
            <Button variant="outline" size="sm" asChild><Link to="/app/chat"><MessagesSquare /> Ask AI</Link></Button>
            <Button size="sm" asChild><Link to="/app/upload"><Upload /> Add report</Link></Button>
            <Button variant="ghost" size="icon-sm" onClick={() => { if (window.confirm(`Remove ${company.name} and its reports?`)) remove.mutate() }} aria-label="Delete company">
              <Trash2 />
            </Button>
          </>
        }
      />

      {done.length === 0 ? (
        <EmptyState icon={FileText} title="No analysed reports yet" description="Upload an annual report to see KPIs, trends and risks."
          action={<Button asChild><Link to="/app/upload"><Upload /> Upload report</Link></Button>} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {HEADLINE.map(([name, label]) => {
              const { now, prev } = latest(name)
              return (
                <StatTile key={name} label={label}
                  value={now ? formatKPI(now.value, null, now.unit_scale, name) : '—'}
                  trend={<Delta value={pctChange(now?.value, prev?.value)} />}
                  sub={now ? `FY${now.fiscal_year}${prev ? ` vs FY${prev.fiscal_year}` : ''}` : 'not reported'} />
              )
            })}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>KPI trend</CardTitle>
                  <CardDescription>{series.length} year{series.length === 1 ? '' : 's'} of reported data</CardDescription>
                </div>
                <Select value={active || ''} onChange={(e) => setMetric(e.target.value)} className="h-8 w-56 text-[13px]">
                  {metrics.map((m) => <option key={m}>{m}</option>)}
                </Select>
              </CardHeader>
              <CardContent className="h-[280px]">
                <ResponsiveContainer>
                  <AreaChart data={series} margin={{ left: -8, right: 12, top: 8 }}>
                    <defs>
                      <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={CHART[0]} stopOpacity={0.25} />
                        <stop offset="100%" stopColor={CHART[0]} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid {...gridProps} />
                    <XAxis dataKey="year" {...axisProps} />
                    <YAxis {...axisProps} tickFormatter={(v) => new Intl.NumberFormat('en-IN', { notation: 'compact' }).format(v)} />
                    <Tooltip content={<ChartTooltip formatter={(v) => formatNumber(v)} />} />
                    <Area type="monotone" dataKey="value" name={active} stroke={CHART[0]} strokeWidth={2} fill="url(#trendFill)"
                      dot={{ r: 4, fill: 'hsl(var(--background))', strokeWidth: 2 }} activeDot={{ r: 5 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Findings per report</CardTitle>
                  <CardDescription>KPIs, risks and footnote flags</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="h-[280px]">
                <ResponsiveContainer>
                  <BarChart data={filings.map((f) => ({ year: `FY${f.fiscal_year}`, KPIs: f.kpi_count, Risks: f.risk_count, Flags: f.flag_count }))} margin={{ left: -20 }}>
                    <CartesianGrid {...gridProps} />
                    <XAxis dataKey="year" {...axisProps} />
                    <YAxis {...axisProps} allowDecimals={false} />
                    <Tooltip cursor={{ fill: 'hsl(var(--muted))' }} content={<ChartTooltip />} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="KPIs" fill={CHART[0]} radius={[3, 3, 0, 0]} maxBarSize={28} />
                    <Bar dataKey="Risks" fill={CHART[3]} radius={[3, 3, 0, 0]} maxBarSize={28} />
                    <Bar dataKey="Flags" fill={CHART[2]} radius={[3, 3, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Reports</CardTitle></CardHeader>
          <div className="divide-y border-t">
            {[...filings].reverse().map((f) => (
              <Link key={f.filing_id} to={`/app/filings/${f.filing_id}`} className="group flex items-center gap-4 px-5 py-3 hover:bg-accent/40">
                <div className="grid size-9 place-items-center rounded-md border bg-background"><FileText className="size-4 text-muted-foreground" /></div>
                <div className="min-w-0 flex-1">
                  <p className="font-medium group-hover:text-primary">Annual Report FY{f.fiscal_year}</p>
                  <p className="truncate text-[12px] text-muted-foreground">{f.file_name} · {f.page_count ?? '—'} pages</p>
                </div>
                <div className="hidden gap-4 text-[12px] text-muted-foreground sm:flex">
                  <span><b className="tabular text-foreground">{f.kpi_count}</b> KPIs</span>
                  <span><b className="tabular text-foreground">{f.risk_count}</b> risks</span>
                </div>
                <StatusBadge status={f.status} />
                <ArrowUpRight className="size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
              </Link>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Similar companies</CardTitle>
              <CardDescription>By embedding similarity of business descriptions</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {peers?.length ? peers.map((p) => (
              <div key={p.company_id || p.name}>
                <div className="mb-1 flex items-center justify-between text-[13px]">
                  {p.company_id ? <Link to={`/app/companies/${p.company_id}`} className="truncate font-medium hover:text-primary">{p.name}</Link> : <span className="truncate font-medium">{p.name}</span>}
                  <span className="tabular text-[12px] text-muted-foreground">{Math.round((p.score || 0) * 100)}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary/70" style={{ width: `${Math.max(4, (p.score || 0) * 100)}%` }} />
                </div>
              </div>
            )) : <p className="text-[13px] text-muted-foreground">Add more companies to discover peers.</p>}
          </CardContent>
        </Card>
      </div>
    </PageBody>
  )
}
