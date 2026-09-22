/**
 * FootnoteFlagList — data-dense-dashboard + ai-native-ui
 * Expandable cards, blockquote excerpts, semantic severity tokens
 * Accordion: keyboard accessible (ux §1, §8 forms/feedback)
 */
import { AlertTriangle, ChevronDown, ChevronUp, AlertCircle, Info, Zap } from 'lucide-react'
import { useState } from 'react'
import { SeverityBadge } from './StatusBadge'

const FLAG_META = {
  inconsistency:        { label: 'Inconsistency',        icon: AlertCircle, color: 'text-red-500',    bg: 'bg-red-50',    border: 'border-red-100' },
  contingent_liability: { label: 'Contingent Liability', icon: AlertTriangle,color: 'text-orange-500', bg: 'bg-orange-50', border: 'border-orange-100' },
  related_party:        { label: 'Related Party',        icon: Info,        color: 'text-amber-500',  bg: 'bg-amber-50',  border: 'border-amber-100' },
  off_balance_sheet:    { label: 'Off-Balance Sheet',    icon: Info,        color: 'text-yellow-600', bg: 'bg-yellow-50', border: 'border-yellow-100' },
  disclosure_gap:       { label: 'Disclosure Gap',       icon: AlertTriangle,color:'text-orange-500', bg: 'bg-orange-50', border: 'border-orange-100' },
  prior_year_promise:   { label: 'Prior-Year Commitment',icon: Info,        color: 'text-indigo-500', bg: 'bg-indigo-50', border: 'border-indigo-100' },
  anomaly:              { label: 'KPI Anomaly',          icon: Zap,         color: 'text-red-500',    bg: 'bg-red-50',    border: 'border-red-100' },
}

function FlagCard({ flag }) {
  const [open, setOpen] = useState(false)
  const meta = FLAG_META[flag.flag_type] || {
    label: flag.flag_type, icon: AlertTriangle,
    color: 'text-slate-500', bg: 'bg-slate-50', border: 'border-slate-200',
  }
  const Icon = meta.icon
  const expandId = `flag-${flag.id}`

  return (
    <div className={`rounded-lg border ${meta.border} overflow-hidden`}>
      {/* Trigger — keyboard accessible button (ux §1) */}
      <button
        className={`w-full flex items-start gap-3 px-4 py-3 text-left
                    transition-colors duration-100 hover:brightness-95 ${meta.bg}`}
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-controls={expandId}
      >
        <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${meta.color}`} aria-hidden="true" />

        <div className="flex-1 min-w-0">
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className="text-[13px] font-semibold text-slate-800">{flag.title}</span>
            <SeverityBadge severity={flag.severity} />
            <span className={`badge ring-1 ${meta.bg} ${meta.color} ${meta.border}`}>
              {meta.label}
            </span>
            <span className="ml-auto text-[10px] text-slate-400 font-mono flex-shrink-0">
              {flag.ranking_score?.toFixed(2)}
            </span>
          </div>
          {/* Preview — truncated when collapsed */}
          {!open && (
            <p className="text-[12px] text-slate-500 leading-relaxed truncate-2">
              {flag.description}
            </p>
          )}
        </div>

        <div className="flex-shrink-0 ml-2 mt-0.5" aria-hidden="true">
          {open
            ? <ChevronUp  className="w-3.5 h-3.5 text-slate-400" />
            : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          }
        </div>
      </button>

      {/* Expanded body */}
      {open && (
        <div
          id={expandId}
          className="px-4 pb-4 pt-3 bg-white border-t border-slate-100 space-y-3 animate-in"
        >
          <p className="text-[13px] text-slate-700 leading-relaxed">{flag.description}</p>

          {flag.footnote_text && (
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1">
                Footnote excerpt
              </p>
              <blockquote className="text-[12px] bg-slate-50 border-l-2 border-orange-300
                                      pl-3 py-2 text-slate-600 italic leading-relaxed rounded-r">
                {flag.footnote_text}
              </blockquote>
            </div>
          )}

          {flag.narrative_text && (
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1">
                Narrative / current year
              </p>
              <blockquote className="text-[12px] bg-slate-50 border-l-2 border-indigo-300
                                      pl-3 py-2 text-slate-600 italic leading-relaxed rounded-r">
                {flag.narrative_text}
              </blockquote>
            </div>
          )}

          {flag.prior_year_text && (
            <div>
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1">
                Prior-year statement
              </p>
              <blockquote className="text-[12px] bg-slate-50 border-l-2 border-purple-300
                                      pl-3 py-2 text-slate-600 italic leading-relaxed rounded-r">
                {flag.prior_year_text}
              </blockquote>
            </div>
          )}

          {flag.page_number && (
            <p className="text-[11px] text-slate-400">Page {flag.page_number}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function FootnoteFlagList({ flags }) {
  if (!flags?.length) {
    return (
      <div className="text-center py-10">
        <AlertTriangle className="w-8 h-8 text-slate-200 mx-auto mb-2" aria-hidden="true" />
        <p className="text-slate-400 text-sm">No flags detected.</p>
      </div>
    )
  }
  return (
    <div className="space-y-2" role="list" aria-label="Footnote flags">
      {flags.map(flag => <FlagCard key={flag.id} flag={flag} />)}
    </div>
  )
}
