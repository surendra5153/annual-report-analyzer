import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...inputs) => twMerge(clsx(inputs))

const IN = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

/** ₹ crore amount → "₹1,23,456 Cr" / "₹4.2 L Cr" for very large values. */
export function formatCrore(value, { compact = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const abs = Math.abs(value)
  if (compact && abs >= 100000) return `₹${(value / 100000).toFixed(2)} L Cr`
  if (compact && abs >= 1000) return `₹${IN.format(Math.round(value))} Cr`
  return `₹${IN.format(value)} Cr`
}

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(value)
}

/**
 * Format a KPI value. The extractor stores "crores" as the unit for every KPI,
 * so the kind (ratio / % / per-share / money) is inferred from the KPI name too.
 */
export function formatKPI(value, unit, unitScale = 'crores', name = '') {
  if (value === null || value === undefined) return '—'
  const u = (unit || '').toLowerCase()
  const n = name.toLowerCase()
  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)
  // A cleaned unit is authoritative; only raw "crores" KPIs need the name heuristic (whole words —
  // "Operations" contains "ratio")
  const known = ['₹ crore', 'x', '%', '₹/share'].includes(unit)
  if (u === 'x' || (!known && /\bratio\b|\bcoverage\b/.test(n))) return `${formatNumber(value)}×`
  if (u === '%' || (!known && /%|\bmargin\b|\broce\b|\broe\b/.test(n))) return `${formatNumber(value, 1)}%`
  if (u.includes('share') || (!known && /per share|\beps\b/.test(n))) return `${sign}₹${formatNumber(abs)}`
  // Cleaned KPIs are stored in ₹ crore; older/raw ones use the filing's unit scale
  const scale = (u.includes('crore') ? 'crore' : unitScale || 'crores').replace(/s$/, '')
  const suffix = { crore: 'Cr', lakh: 'L', million: 'Mn', billion: 'Bn', thousand: 'K' }[scale] || ''
  return `${sign}₹${formatNumber(abs)}${suffix ? ` ${suffix}` : ''}`
}

const TO_CRORE = { lakh: 0.01, lac: 0.01, million: 0.1, mn: 0.1, billion: 100, bn: 100 }
const AMOUNT_RE = /₹\s?([\d,]+(?:\.\d+)?)\s?(lakhs?|lacs?|millions?|mn|billions?|bn)\b(?!\s*\(\s*≈?\s*₹)/gi

/**
 * Append an exact ₹ crore equivalent to amounts stated in lakh / million / billion:
 * "₹1,207.26 lakh" → "₹1,207.26 lakh (≈ ₹12.07 Cr)". Done in code rather than by the
 * LLM because a 3B model's arithmetic is unreliable.
 */
export function addCroreEquivalents(text) {
  return text.replace(AMOUNT_RE, (match, num, unit) => {
    const key = unit.toLowerCase().replace(/s$/, '')
    const crore = Number(num.replace(/,/g, '')) * TO_CRORE[key]
    if (!Number.isFinite(crore)) return match
    const digits = crore >= 100 ? 0 : 2
    return `${match} (≈ ₹${new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(crore)} Cr)`
  })
}

export function pctChange(curr, prev) {
  if (curr == null || prev == null || prev === 0) return null
  return ((curr - prev) / Math.abs(prev)) * 100
}

export function timeAgo(date) {
  const s = (Date.now() - new Date(date).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export const titleCase = (s = '') => s.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const shortCompany = (name = '') =>
  name.replace(/\b(limited|ltd\.?|private|pvt\.?|corporation|corp\.?|india)\b/gi, '').replace(/\s+/g, ' ').trim()
