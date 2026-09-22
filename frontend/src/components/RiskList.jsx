/**
 * RiskList — data-dense-dashboard + accessible-and-ethical (#8)
 * Semantic color tokens, icon + label (not color-only), 13px body
 */
import { ShieldAlert, Shield, ShieldCheck, Zap, Globe, Truck, Settings } from 'lucide-react'
import { SeverityBadge } from './StatusBadge'

// Category meta — icon AND color (ux §1: not color-only)
const CATEGORY_META = {
  financial:     { icon: ShieldAlert, bg: 'bg-red-50',     border: 'border-red-100',    text: 'text-red-600',    label: 'Financial' },
  regulatory:    { icon: Shield,      bg: 'bg-purple-50',  border: 'border-purple-100', text: 'text-purple-600', label: 'Regulatory' },
  cybersecurity: { icon: Zap,         bg: 'bg-orange-50',  border: 'border-orange-100', text: 'text-orange-600', label: 'Cybersecurity' },
  climate:       { icon: Globe,       bg: 'bg-emerald-50', border: 'border-emerald-100',text: 'text-emerald-600',label: 'Climate' },
  supply_chain:  { icon: Truck,       bg: 'bg-amber-50',   border: 'border-amber-100',  text: 'text-amber-600',  label: 'Supply Chain' },
  operational:   { icon: Settings,    bg: 'bg-blue-50',    border: 'border-blue-100',   text: 'text-blue-600',   label: 'Operational' },
  other:         { icon: ShieldCheck, bg: 'bg-slate-50',   border: 'border-slate-100',  text: 'text-slate-500',  label: 'Other' },
}

export default function RiskList({ risks }) {
  if (!risks?.length) {
    return (
      <div className="text-center py-10">
        <ShieldCheck className="w-8 h-8 text-slate-200 mx-auto mb-2" aria-hidden="true" />
        <p className="text-slate-400 text-sm">No risks classified yet.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2.5" role="list" aria-label="Risk factors">
      {risks.map(risk => {
        const meta = CATEGORY_META[risk.category] || CATEGORY_META.other
        const Icon = meta.icon
        return (
          <div
            key={risk.id}
            className={`rounded-lg border ${meta.border} ${meta.bg} p-4`}
            role="listitem"
          >
            <div className="flex items-start gap-3">
              {/* Icon — not color-only indicator (ux §1) */}
              <Icon
                className={`w-4 h-4 mt-0.5 flex-shrink-0 ${meta.text}`}
                aria-hidden="true"
              />
              <div className="flex-1 min-w-0">
                {/* Header row */}
                <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
                  <span className="text-sm font-semibold text-slate-800">{risk.title}</span>
                  <SeverityBadge severity={risk.severity} />
                  <span className={`badge ${meta.bg} ${meta.text} ring-1 ${meta.border}`}>
                    {meta.label}
                  </span>
                </div>
                {/* Description — 13px, 1.5 line-height (ux §6) */}
                <p className="text-[13px] text-slate-600 leading-relaxed">{risk.description}</p>
                {risk.page_number > 0 && (
                  <p className="text-[11px] text-slate-400 mt-1.5">
                    Page {risk.page_number}
                  </p>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
