import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Check, GitCompareArrows, Loader2 } from 'lucide-react'
import { compareFilings, getCompanies, getFilings } from '@/services/api'
import { PageBody, PageHeader } from '@/components/app/AppShell'
import { axisProps, CHART, ChartTooltip, gridProps } from '@/components/app/domain'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { EmptyState } from '@/components/ui/misc'
import { cn, formatNumber, shortCompany } from '@/lib/utils'

const usdMn = (v) => v / 1e6

export default function Compare() {
  const { data: companies = [] } = useQuery({ queryKey: ['companies'], queryFn: getCompanies })
  const { data: filings = [] } = useQuery({ queryKey: ['filings-all'], queryFn: () => getFilings() })
  const [selected, setSelected] = useState([])
  const [view, setView] = useState('charts')
  const cmp = useMutation({ mutationFn: () => compareFilings(selected, null) })

  const name = useMemo(() => Object.fromEntries(companies.map((c) => [c.id, c.name])), [companies])
  const ready = filings.filter((f) => f.status === 'completed').sort((a, b) => (name[a.company_id] || '').localeCompare(name[b.company_id] || '') || b.fiscal_year - a.fiscal_year)
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  // Only KPIs reported by at least two of the selected filings are comparable
  const results = (cmp.data || []).filter((r) => r.chart_data.length >= 2)
  const columns = [...new Set(results.flatMap((r) => r.chart_data.map((d) => d.label)))]

  return (
    <PageBody>
      <PageHeader title="Compare" description="Side-by-side KPIs across companies and years, normalised to a common currency scale." />

      <Card className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[13px] font-medium">Select reports <span className="text-muted-foreground">({selected.length} selected)</span></p>
          <Button size="sm" disabled={selected.length < 2 || cmp.isPending} onClick={() => cmp.mutate()}>
            {cmp.isPending ? <Loader2 className="animate-spin" /> : <GitCompareArrows />} Compare
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {ready.map((f) => {
            const on = selected.includes(f.id)
            return (
              <button key={f.id} onClick={() => toggle(f.id)}
                className={cn('inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-[13px] transition-colors',
                  on ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground hover:border-foreground/20 hover:text-foreground')}>
                <span className={cn('grid size-3.5 place-items-center rounded-sm border', on && 'border-primary bg-primary text-primary-foreground')}>
                  {on && <Check className="size-2.5" />}
                </span>
                {shortCompany(name[f.company_id] || f.file_name)} <span className="opacity-70">FY{f.fiscal_year}</span>
              </button>
            )
          })}
        </div>
      </Card>

      {!cmp.data ? (
        <EmptyState icon={GitCompareArrows} title="Pick two or more reports" description="Compare the same company across years, or different companies in the same year." />
      ) : !results.length ? (
        <EmptyState icon={GitCompareArrows} title="No common KPIs" description="The selected reports do not share any extracted KPI." />
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="text-[13px] text-muted-foreground">{results.length} comparable KPIs · charts in USD millions (normalised), table as reported</p>
            <Tabs value={view} onValueChange={setView}>
              <TabsList><TabsTrigger value="charts">Charts</TabsTrigger><TabsTrigger value="table">Table</TabsTrigger></TabsList>
            </Tabs>
          </div>

          {view === 'charts' ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {results.map((r) => {
                // Ratios / % / per-share KPIs are scale-free — plot them as-is
                const unit = r.chart_data[0]?.unit_scale
                const scaleFree = ['x', '%', '₹/share'].includes(unit)
                const fmt = scaleFree ? (v) => `${formatNumber(v)}${unit === 'x' ? '×' : unit === '%' ? '%' : ''}` : (v) => `$${formatNumber(v)} Mn`
                const data = r.chart_data.map((d) => ({ ...d, usd: scaleFree ? d.value : usdMn(d.value) }))
                return (
                  <Card key={r.kpi_name}>
                    <CardHeader className="pb-1">
                      <div>
                        <CardTitle className="text-[14px]">{r.kpi_name}</CardTitle>
                        <CardDescription>{data.length} reports · {scaleFree ? (unit === 'x' ? 'ratio' : unit) : 'USD Mn (normalised)'}</CardDescription>
                      </div>
                    </CardHeader>
                    <CardContent className="h-[200px]">
                      <ResponsiveContainer>
                        <BarChart data={data} margin={{ left: -12, right: 4 }}>
                          <CartesianGrid {...gridProps} />
                          <XAxis dataKey="label" {...axisProps} tickFormatter={(l) => l.split(' ')[0]} interval={0} fontSize={10} />
                          <YAxis {...axisProps} tickFormatter={(v) => new Intl.NumberFormat('en', { notation: 'compact' }).format(v)} />
                          <Tooltip cursor={{ fill: 'hsl(var(--muted))' }}
                            content={<ChartTooltip formatter={fmt} />} />
                          <Bar dataKey="usd" name={scaleFree ? (unit === '₹/share' ? '₹ per share' : unit) : 'USD Mn'} radius={[4, 4, 0, 0]} maxBarSize={40}>
                            {data.map((d, i) => <Cell key={d.label} fill={CHART[i % CHART.length]} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          ) : (
            <Card className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b bg-muted/40 text-[12px] text-muted-foreground">
                    <th className="sticky left-0 bg-muted/40 px-5 py-2 text-left font-medium">KPI</th>
                    {columns.map((c) => <th key={c} className="whitespace-nowrap px-4 py-2 text-right font-medium">{c}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {results.map((r) => (
                    <tr key={r.kpi_name} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="sticky left-0 bg-card px-5 py-2.5 font-medium">{r.kpi_name}</td>
                      {columns.map((c) => {
                        const d = r.chart_data.find((x) => x.label === c)
                        return (
                          <td key={c} className="tabular whitespace-nowrap px-4 py-2.5 text-right">
                            {d ? <>{formatNumber(d.raw_value)} <span className="text-[11px] text-muted-foreground">{d.unit_scale}</span></> : '—'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </PageBody>
  )
}
