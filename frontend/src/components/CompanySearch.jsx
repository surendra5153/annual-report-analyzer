import { useState, useRef, useEffect, useMemo } from 'react'
import { Search, Building2, X } from 'lucide-react'
import NSE_COMPANIES from '../data/nse_companies.json'

/**
 * Searchable autocomplete over all NSE-listed companies.
 *
 * Props:
 *   value        – currently selected company object { ticker, name, exchange, sector } or null
 *   onChange     – called with the selected company object (or null on clear)
 *   placeholder  – input placeholder text
 *   disabled     – boolean
 */
export default function CompanySearch({ value, onChange, placeholder = 'Search company or ticker…', disabled = false }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)

  // Filter list based on query — match name prefix first, then substring, then ticker
  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q || q.length < 1) return []

    const namePrefix = []
    const nameSubstr = []
    const tickerMatch = []
    const seen = new Set()

    for (const c of NSE_COMPANIES) {
      const nameLower = c.name.toLowerCase()
      const tickerLower = c.ticker.toLowerCase()
      if (nameLower.startsWith(q)) namePrefix.push(c)
      else if (nameLower.includes(q)) nameSubstr.push(c)
      else if (tickerLower.startsWith(q) || tickerLower === q) tickerMatch.push(c)
    }

    const merged = [...namePrefix, ...tickerMatch, ...nameSubstr]
    const unique = merged.filter(c => {
      if (seen.has(c.ticker)) return false
      seen.add(c.ticker)
      return true
    })
    return unique.slice(0, 10)
  }, [query])

  // When a company is already selected, show its name in the input
  useEffect(() => {
    if (value && !open) setQuery('')
  }, [value, open])

  const select = (company) => {
    onChange(company)
    setQuery('')
    setOpen(false)
    inputRef.current?.blur()
  }

  const clear = (e) => {
    e.stopPropagation()
    onChange(null)
    setQuery('')
    setOpen(false)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleKeyDown = (e) => {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted(h => Math.min(h + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted(h => Math.max(h - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (results[highlighted]) select(results[highlighted])
    } else if (e.key === 'Escape') {
      setOpen(false)
      setQuery('')
    }
  }

  // Scroll highlighted item into view
  useEffect(() => {
    const el = listRef.current?.children[highlighted]
    el?.scrollIntoView({ block: 'nearest' })
  }, [highlighted])

  // Reset highlight when results change
  useEffect(() => { setHighlighted(0) }, [results])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (!inputRef.current?.closest('.company-search-root')?.contains(e.target)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="company-search-root relative">
      {/* Selected pill */}
      {value && !open ? (
        <div className="flex items-center gap-2 border border-primary-300 bg-primary-50 rounded-lg px-3 py-2">
          <Building2 className="w-4 h-4 text-primary-500 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-gray-900">{value.name}</span>
            <span className="ml-2 text-xs text-gray-500">{value.ticker}</span>
            {value.sector && <span className="ml-2 text-xs text-primary-600">{value.sector}</span>}
          </div>
          <button
            type="button"
            onClick={clear}
            disabled={disabled}
            className="text-gray-400 hover:text-gray-600 flex-shrink-0"
            aria-label="Clear selection"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          <input
            ref={inputRef}
            type="text"
            className="w-full border rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 disabled:bg-gray-50 disabled:cursor-not-allowed"
            placeholder={placeholder}
            value={query}
            disabled={disabled}
            onChange={e => { setQuery(e.target.value); setOpen(true) }}
            onFocus={() => { if (query) setOpen(true) }}
            onKeyDown={handleKeyDown}
            autoComplete="off"
          />
        </div>
      )}

      {/* Dropdown */}
      {open && results.length > 0 && (
        <ul
          ref={listRef}
          className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg max-h-64 overflow-y-auto"
          role="listbox"
        >
          {results.map((company, idx) => (
            <li
              key={company.ticker}
              role="option"
              aria-selected={idx === highlighted}
              className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors ${
                idx === highlighted ? 'bg-primary-50' : 'hover:bg-gray-50'
              }`}
              onMouseDown={() => select(company)}
              onMouseEnter={() => setHighlighted(idx)}
            >
              <div className="w-8 h-8 rounded-md bg-gray-100 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-bold text-gray-500">{company.ticker.slice(0, 2)}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{company.name}</p>
                <p className="text-xs text-gray-500">
                  <span className="font-mono">{company.ticker}</span>
                  {company.sector && <> · {company.sector}</>}
                  <span className="ml-1 text-gray-400">{company.exchange}</span>
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {open && query.trim().length > 0 && results.length === 0 && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-lg px-4 py-3 text-sm text-gray-500">
          No listed company found for "{query}"
        </div>
      )}
    </div>
  )
}
