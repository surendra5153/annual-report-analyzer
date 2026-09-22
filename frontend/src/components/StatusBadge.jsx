import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'

const STATUS = {
  pending:    { label: 'Pending',    color: '#fbbf24', bg: 'rgba(251,191,36,0.1)',   Icon: Clock },
  processing: { label: 'Processing', color: '#818cf8', bg: 'rgba(129,140,248,0.1)', Icon: Loader2, spin: true },
  completed:  { label: 'Completed',  color: '#34d399', bg: 'rgba(52,211,153,0.1)',  Icon: CheckCircle2 },
  failed:     { label: 'Failed',     color: '#f87171', bg: 'rgba(248,113,113,0.1)', Icon: XCircle },
}

const SEV = {
  low:      { label: 'Low',      color: '#555',    bg: 'rgba(255,255,255,0.05)' },
  medium:   { label: 'Medium',   color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
  high:     { label: 'High',     color: '#f97316', bg: 'rgba(249,115,22,0.1)' },
  critical: { label: 'Critical', color: '#f87171', bg: 'rgba(248,113,113,0.12)' },
}

const CONF = {
  high:   { color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
  medium: { color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
  low:    { color: '#555',    bg: 'rgba(255,255,255,0.05)' },
}

const pill = (color, bg, content) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color, background: bg, borderRadius: 5, padding: '2px 8px' }}>
    {content}
  </span>
)

export function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.pending
  return pill(s.color, s.bg, (
    <>
      <s.Icon style={{ width: 10, height: 10, ...(s.spin ? { animation: 'spin 1s linear infinite' } : {}) }} />
      {s.label}
    </>
  ))
}

export function SeverityBadge({ severity }) {
  const s = SEV[severity?.toLowerCase()] || SEV.medium
  return pill(s.color, s.bg, s.label)
}

export function ConfidenceBadge({ confidence }) {
  const c = CONF[confidence] || CONF.medium
  return pill(c.color, c.bg, (
    <>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.color }} />
      {confidence}
    </>
  ))
}
