import { useMemo, useRef, useState } from 'react'
import { Building2, Search, X } from 'lucide-react'
import NSE_COMPANIES from '@/data/nse_companies.json'
import { cn } from '@/lib/utils'

/**
 * Searchable picker over all NSE-listed companies.
 * value: { ticker, name, sector } | null — onChange(company | null)
 */
export default function CompanyPicker({ value, onChange, placeholder = 'Search company or ticker…', className }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(0)
  const inputRef = useRef(null)

  const results = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return []
    const score = (c) => {
      const n = c.name.toLowerCase()
      const t = c.ticker.toLowerCase()
      if (t === s) return 0
      if (n.startsWith(s)) return 1
      if (t.startsWith(s)) return 2
      if (n.includes(s)) return 3
      return 9
    }
    return NSE_COMPANIES.map((c) => [score(c), c]).filter(([sc]) => sc < 9).sort((a, b) => a[0] - b[0]).slice(0, 8).map(([, c]) => c)
  }, [q])

  const pick = (c) => {
    onChange(c)
    setQ('')
    setOpen(false)
  }

  if (value) {
    return (
      <div className={cn('flex h-10 items-center gap-2.5 rounded-md border bg-background px-3', className)}>
        <Building2 className="size-4 text-muted-foreground" />
        <span className="flex-1 truncate text-sm font-medium">{value.name}</span>
        <span className="font-mono text-[11px] text-muted-foreground">{value.ticker}</span>
        <button onClick={() => onChange(null)} className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground" aria-label="Clear">
          <X className="size-3.5" />
        </button>
      </div>
    )
  }

  return (
    <div className={cn('relative', className)}>
      <div className="flex h-10 items-center gap-2 rounded-md border bg-background px-3 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30">
        <Search className="size-4 text-muted-foreground" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); setHi(0) }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(results.length - 1, h + 1)) }
            if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(0, h - 1)) }
            if (e.key === 'Enter' && results[hi]) { e.preventDefault(); pick(results[hi]) }
            if (e.key === 'Escape') setOpen(false)
          }}
          placeholder={placeholder}
          className="h-full flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      {open && results.length > 0 && (
        <ul className="absolute z-50 mt-1.5 w-full overflow-hidden rounded-lg border bg-popover p-1 shadow-lift">
          {results.map((c, i) => (
            <li key={c.ticker}>
              <button
                onMouseDown={(e) => { e.preventDefault(); pick(c) }}
                onMouseEnter={() => setHi(i)}
                className={cn('flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left', i === hi && 'bg-accent')}
              >
                <span className="flex-1 truncate text-[13px]">{c.name}</span>
                <span className="truncate text-[11px] text-muted-foreground">{c.sector}</span>
                <span className="w-20 text-right font-mono text-[11px] text-muted-foreground">{c.ticker}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
