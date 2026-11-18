import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, ArrowRight, Building2, FileStack, Gauge, ShieldAlert, Upload } from 'lucide-react'
import { getCompanies, getFilings, getJobByFiling, getKPIs, getRisks } from '@/services/api'
import { PageBody, PageHeader } from '@/components/app/AppShell'
import { axisProps, CHART, ChartTooltip, gridProps, pickKPI, RISK_COLORS, StatTile, StatusBadge } from '@/components/app/domain'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { SeverityBadge } from '@/components/ui/badge'
import { EmptyState, Progress, Skeleton } from '@/components/ui/misc'
import { formatNumber, shortCompany, timeAgo, titleCase } from '@/lib/utils'

const SEV_RANK = { critical: 0, high: 1, medium: 2, low: 3 }

export default function Overview() {
  const { data: companies = [], isLoading: lc } = useQuery({ queryKey: ['companies'], queryFn: getCompanies })
  const { data: filings = [], isLoading: lf } = useQuery({
    queryKey: ['filings-all'],
    queryFn: () => getFilings(),
    refetchInterval: (q) => (q.state.data?.some((f) => f.status === 'processing' || f.status === 'pending') ? 4000 : 30000),
  })

  const completed = filings.filter((f) => f.status === 'completed')
  const inFlight = filings.filter((f) => f.status === 'processing' || f.status === 'pending')
  const companyById = useMemo(() => Object.fromEntries(companies.map((c) => [c.id, c])), [companies])

  const kpiQs = useQueries({ queries: completed.map((f) => ({ queryKey: ['kpis', f.id], queryFn: () => getKPIs(f.id) })) })
  const riskQs = useQueries({ queries: completed.map((f) => ({ queryKey: ['risks', f.id], queryFn: () => getRisks(f.id) })) })
  const jobQs = useQueries({
    queries: inFlight.map((f) => ({ queryKey: ['job', f.id], queryFn: () => getJobByFiling(f.id), refetchInterval: 2500 })),
  })

  const kpisByFiling = Object.fromEntries(completed.map((f, i) => [f.id, kpiQs[i]?.data || []]))
  const risks = completed.flatMap((f, i) =>
    (riskQs[i]?.data || []).map((r) => ({ ...r, filing: f, company: companyById[f.company_id] }))
  )

  // Latest completed report per company → revenue / PAT snapshot
  const snapshot = useMemo(() => {
    const latest = {}
    for (const f of completed) if (!latest[f.company_id] || f.fiscal_year > latest[f.company_id].fiscal_year) latest[f.company_id] = f
    return Object.values(latest)
      .map((f) => {
        const k = kpisByFiling[f.id] || []
        return {
          name: shortCompany(companyById[f.company_id]?.name || f.file_name).split(' ').slice(0, 2).join(' '),
          year: f.fiscal_year,
          unit: f.unit_scale,
          Revenue: pickKPI(k, 'revenue')?.value ?? null,
          'Net profit': pickKPI(k, 'pat')?.value ?? null,
        }
      })
      .filter((d) => d.Revenue !== null)
  }, [completed, kpisByFiling, companyById])

  const riskMix = useMemo(() => {
    const c = {}
    for (const r of risks) c[r.category] = (c[r.category] || 0) + 1
    return Object.entries(c).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)
  }, [risks])

  const totalKpis = Object.values(kpisByFiling).flat()
  const verifiedPct = totalKpis.length ? (100 * totalKpis.filter((k) => k.is_verified).length) / totalKpis.length : 0
  const highRisks = risks.filter((r) => r.severity === 'high' || r.severity === 'critical')
  const pages = completed.reduce((s, f) => s + (f.page_count || 0), 0)
  const loading = lc || lf

  if (!loading && filings.length === 0) {
    return (
      <PageBody>
        <PageHeader title="Overview" description="Your annual-report intelligence workspace." />
        <EmptyState
          icon={FileStack}
          title="No reports yet"
          description="Upload an annual report PDF. It is parsed, indexed and analysed entirely on your machine."
          action={<Button asChild><Link to="/app/upload"><Upload /> Upload your first report</Link></Button>}
          className="py-20"
        />
      </PageBody>
    )
  }

  return (
    <PageBody>
      <PageHeader
        title="Overview"
        description={`${companies.length} companies · ${completed.length} reports analysed on local models`}
        actions={<Button variant="outline" size="sm" asChild><Link to="/app/compare">Compare companies <ArrowRight /></Link></Button>}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[118px]" />)
        ) : (
          <>
            <StatTile label="Companies" value={companies.length} icon={Building2}
              sub={`${companies.filter((c) => c.is_tracked).length} tracked`} />
            <StatTile label="Reports analysed" value={completed.length} icon={FileStack}
              sub={`${formatNumber(pages, 0)} pages parsed`} />
            <StatTile label="KPIs extracted" value={formatNumber(totalKpis.length, 0)} icon={Gauge}
              sub={`${verifiedPct.toFixed(0)}% passed verification`} />
            <StatTile label="High-severity risks" value={highRisks.length} icon={ShieldAlert}
              sub={`of ${risks.length} risks identified`} />
          </>
        )}
      </div>

      {inFlight.length > 0 && (
        <Card className="border-primary/30 bg-primary/[.03]">
          <CardHeader className="pb-2">
            <div>
              <CardTitle>Processing</CardTitle>
              <CardDescription>Reports currently moving through the local pipeline</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {inFlight.map((f, i) => {
              const job = jobQs[i]?.data
              return (
                <Link key={f.id} to={`/app/filings/${f.id}`} className="block rounded-md p-2 -mx-2 hover:bg-accent/60">
                  <div className="mb-1.5 flex items-center justify-between text-[13px]">
                    <span className="font-medium">{companyById[f.company_id]?.name || f.file_name} · FY{f.fiscal_year}</span>
                    <span className="text-muted-foreground">{titleCase(job?.stage || 'queued')} · {job?.progress_pct ?? 0}%</span>
                  </div>
                  <Progress value={job?.progress_pct ?? 2} />
                </Link>
              )
            })}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Financial snapshot</CardTitle>
              <CardDescription>Revenue vs net profit (₹ crore), latest report per company</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="h-[300px]">
            {snapshot.length ? (
              <ResponsiveContainer>
                <BarChart data={snapshot} barGap={4} margin={{ left: -8, right: 8 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="name" {...axisProps} />
                  <YAxis {...axisProps} tickFormatter={(v) => new Intl.NumberFormat('en-IN', { notation: 'compact' }).format(v)} />
                  <Tooltip cursor={{ fill: 'hsl(var(--muted))' }}
                    content={<ChartTooltip formatter={(v) => `₹${formatNumber(v)} Cr`} labelFormatter={(l) => {
                      const d = snapshot.find((s) => s.name === l)
                      return `${l} · FY${d?.year}`
                    }} />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Revenue" fill={CHART[0]} radius={[4, 4, 0, 0]} maxBarSize={44} />
                  <Bar dataKey="Net profit" fill={CHART[1]} radius={[4, 4, 0, 0]} maxBarSize={44} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Skeleton className="h-full" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Risk mix</CardTitle>
              <CardDescription>All identified risks by category</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="flex h-[300px] flex-col">
            {riskMix.length ? (
              <>
                <div className="relative h-[170px]">
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={riskMix} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={2} strokeWidth={0}>
                        {riskMix.map((r) => <Cell key={r.name} fill={RISK_COLORS[r.name] || CHART[4]} />)}
                      </Pie>
                      <Tooltip content={<ChartTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
                    <div>
                      <p className="tabular text-2xl font-semibold">{risks.length}</p>
                      <p className="text-[11px] text-muted-foreground">risks</p>
                    </div>
                  </div>
                </div>
                <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12px]">
                  {riskMix.map((r) => (
                    <li key={r.name} className="flex items-center gap-2">
                      <span className="size-2 rounded-sm" style={{ background: RISK_COLORS[r.name] }} />
                      <span className="truncate text-muted-foreground">{titleCase(r.name)}</span>
                      <span className="tabular ml-auto font-medium">{r.value}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <Skeleton className="h-full" />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <div>
              <CardTitle>Reports</CardTitle>
              <CardDescription>Every uploaded annual report</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild><Link to="/app/companies">All companies <ArrowRight /></Link></Button>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-y bg-muted/40 text-left text-[12px] text-muted-foreground">
                  <th className="px-5 py-2 font-medium">Company</th>
                  <th className="px-3 py-2 font-medium">Year</th>
                  <th className="px-3 py-2 text-right font-medium">Pages</th>
                  <th className="px-3 py-2 text-right font-medium">KPIs</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-5 py-2 text-right font-medium">Added</th>
                </tr>
              </thead>
              <tbody>
                {[...filings].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).map((f) => (
                  <tr key={f.id} className="group border-b last:border-0 hover:bg-accent/50">
                    <td className="px-5 py-2.5">
                      <Link to={`/app/filings/${f.id}`} className="font-medium group-hover:text-primary">
                        {companyById[f.company_id]?.name || f.file_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">FY{f.fiscal_year}</td>
                    <td className="tabular px-3 py-2.5 text-right">{f.page_count ?? '—'}</td>
                    <td className="tabular px-3 py-2.5 text-right">{kpisByFiling[f.id]?.length ?? '—'}</td>
                    <td className="px-3 py-2.5"><StatusBadge status={f.status} /></td>
                    <td className="px-5 py-2.5 text-right text-muted-foreground">{timeAgo(f.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>Risk feed</CardTitle>
              <CardDescription>Most severe risks across all reports</CardDescription>
            </div>
            <AlertTriangle className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-1 px-3">
            {[...risks].sort((a, b) => SEV_RANK[a.severity] - SEV_RANK[b.severity]).slice(0, 7).map((r) => (
              <Link key={r.id} to={`/app/filings/${r.filing.id}?tab=risks`} className="block rounded-md px-2 py-2 hover:bg-accent/60">
                <div className="flex items-start justify-between gap-3">
                  <p className="line-clamp-1 text-[13px] font-medium">{r.title}</p>
                  <SeverityBadge severity={r.severity} />
                </div>
                <p className="mt-0.5 text-[12px] text-muted-foreground">
                  {shortCompany(r.company?.name || '')} · FY{r.filing.fiscal_year} · {titleCase(r.category)}
                  {r.page_number ? ` · p.${r.page_number}` : ''}
                </p>
              </Link>
            ))}
            {!risks.length && <p className="px-2 py-6 text-center text-[13px] text-muted-foreground">No risks yet.</p>}
          </CardContent>
        </Card>
      </div>
    </PageBody>
  )
}
