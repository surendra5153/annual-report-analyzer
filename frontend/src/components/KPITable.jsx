import { useState } from 'react'
import { CheckCircle2, AlertTriangle } from 'lucide-react'

const CAT_COLORS = {
  Revenue: 'text-blue-400 bg-blue-500/10',
  Profitability: 'text-emerald-400 bg-emerald-500/10',
  'Balance Sheet': 'text-purple-400 bg-purple-500/10',
  'Cash Flow': 'text-amber-400 bg-amber-500/10',
  Ratios: 'text-pink-400 bg-pink-500/10',
  'Per Share': 'text-indigo-400 bg-indigo-500/10',
  Other: 'text-slate-400 bg-slate-500/10',
}

export default function KPITable({ kpis }) {
  const [filter, setFilter] = useState('All')

  if (!kpis?.length)
    return (
      <div className="text-center py-12 text-slate-500 text-sm">
        No KPIs extracted yet.
      </div>
    )

  const cats = ['All', ...new Set(kpis.map((k) => k.category).filter(Boolean))]
  const filtered = filter === 'All' ? kpis : kpis.filter((k) => k.category === filter)
  const verifiedCount = kpis.filter((k) => k.is_verified).length

  return (
    <div>
      {/* Summary */}
      <div className="flex items-center gap-4 mb-4 text-xs">
        <span className="text-slate-400 font-semibold">{kpis.length} extracted</span>
        <span className="text-emerald-400 font-semibold">{verifiedCount} verified</span>
        {kpis.length - verifiedCount > 0 && (
          <span className="text-amber-400 font-semibold">
            {kpis.length - verifiedCount} unverified
          </span>
        )}
      </div>

      {/* Filter pills - Full width spread */}
      <div className="flex flex-wrap gap-2 mb-6">
        {cats.map((c) => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className={`text-xs font-bold uppercase tracking-wider px-4 py-2 rounded-lg transition-all ${
              filter === c
                ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/30'
                : 'bg-white/[0.05] hover:bg-white/[0.08] text-slate-400 hover:text-slate-300 border border-white/10'
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Table - Full width with hover states */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b-2 border-white/[0.08]">
              <th className="text-left py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-2/5">
                Metric
              </th>
              <th className="text-right py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-1/5">
                Value
              </th>
              <th className="text-left py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-1/6">
                Unit
              </th>
              <th className="text-left py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-1/6">
                Category
              </th>
              <th className="text-center py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-16">
                Verified
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((kpi) => (
              <tr
                key={kpi.id}
                className="border-b border-white/[0.08] hover:bg-white/[0.02] transition-colors cursor-pointer"
              >
                <td className="py-3 px-4">
                  <div className="flex flex-col">
                    <span className="text-sm text-slate-200 font-medium">{kpi.name}</span>
                    {kpi.page_number && (
                      <span className="text-xs text-slate-600 font-mono mt-0.5">
                        p.{kpi.page_number}
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-3 px-4 text-right font-mono tabular-nums text-sm font-semibold text-slate-100">
                  {kpi.value != null ? (
                    kpi.value.toLocaleString('en-IN', { maximumFractionDigits: 2 })
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="py-3 px-4 text-xs text-slate-400 font-mono">
                  {kpi.unit || kpi.currency || '—'}
                </td>
                <td className="py-3 px-4">
                  {kpi.category && (
                    <span
                      className={`text-[10px] font-bold px-2.5 py-1 rounded uppercase tracking-wider ${
                        CAT_COLORS[kpi.category] || CAT_COLORS.Other
                      }`}
                    >
                      {kpi.category}
                    </span>
                  )}
                </td>
                <td className="py-3 px-4 text-center">
                  {kpi.is_verified ? (
                    <CheckCircle2
                      className="w-4 h-4 text-emerald-400 mx-auto"
                      title={kpi.verification_note}
                    />
                  ) : (
                    <AlertTriangle
                      className="w-4 h-4 text-amber-400 mx-auto"
                      title={kpi.verification_note}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
