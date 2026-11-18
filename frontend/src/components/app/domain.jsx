import { CheckCircle2, CircleDashed, Loader2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export const CHART = ['hsl(var(--chart-1))', 'hsl(var(--chart-2))', 'hsl(var(--chart-3))', 'hsl(var(--chart-4))', 'hsl(var(--chart-5))']

export const axisProps = {
  stroke: 'hsl(var(--muted-foreground))',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
}

export const gridProps = { stroke: 'hsl(var(--border))', strokeDasharray: '3 3', vertical: false }

/** Recharts tooltip matching the design system. */
export function ChartTooltip({ active, payload, label, formatter = (v) => v, labelFormatter }) {
  if (!active || !payload?.length) return null
  return (
    <div className="min-w-[160px] rounded-lg border bg-popover px-3 py-2 text-[12px] shadow-lift">
      {label !== undefined && (
        <p className="mb-1.5 font-medium">{labelFormatter ? labelFormatter(label) : label}</p>
      )}
      <div className="space-y-1">
        {payload.map((p) => (
          <div key={p.dataKey + p.name} className="flex items-center gap-2">
            <span className="size-2 rounded-sm" style={{ background: p.color || p.fill }} />
            <span className="text-muted-foreground">{p.name}</span>
            <span className="tabular ml-auto font-medium">{formatter(p.value, p.name)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const STATUS = {
  completed: { variant: 'success', icon: CheckCircle2, label: 'Ready' },
  processing: { variant: 'default', icon: Loader2, label: 'Processing', spin: true },
  pending: { variant: 'secondary', icon: CircleDashed, label: 'Queued' },
  failed: { variant: 'danger', icon: XCircle, label: 'Failed' },
}

export function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.pending
  return (
    <Badge variant={s.variant}>
      <s.icon className={cn(s.spin && 'animate-spin')} />
      {s.label}
    </Badge>
  )
}

export function StatTile({ label, value, sub, icon: Icon, trend, className }) {
  return (
    <Card className={cn('p-5', className)}>
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
        {Icon && <Icon className="size-4 text-muted-foreground" />}
      </div>
      <p className="tabular mt-2 text-[26px] font-semibold leading-none tracking-tight">{value}</p>
      <div className="mt-2 flex items-center gap-2 text-[12px] text-muted-foreground">
        {trend}
        {sub}
      </div>
    </Card>
  )
}

/** Picks headline figures out of a KPI list. */
export const KPI_NAMES = {
  revenue: ['Total Revenue', 'Revenue from Operations'],
  pat: ['Profit After Tax (PAT) / Net Profit'],
  ebitda: ['EBITDA'],
  assets: ['Total Assets'],
  equity: ['Total Equity / Shareholders Equity'],
  debt: ['Debt (Total Borrowings)'],
  eps: ['Earnings Per Share (EPS)'],
}

export function pickKPI(kpis = [], key) {
  for (const name of KPI_NAMES[key] || [key]) {
    const k = kpis.find((x) => x.name === name && x.value !== null)
    if (k) return k
  }
  return null
}

export const RISK_COLORS = {
  financial: 'hsl(var(--chart-1))',
  regulatory: 'hsl(var(--chart-5))',
  cybersecurity: 'hsl(var(--chart-4))',
  climate: 'hsl(var(--chart-2))',
  supply_chain: 'hsl(var(--chart-3))',
  operational: 'hsl(240 5% 55%)',
  other: 'hsl(240 5% 70%)',
}
