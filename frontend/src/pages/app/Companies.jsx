import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Building2, LayoutGrid, List, MoreHorizontal, Plus, Search, Star, Trash2 } from 'lucide-react'
import { createCompany, deleteCompany, getCompanies, getFilings, updateCompany } from '@/services/api'
import { PageBody, PageHeader } from '@/components/app/AppShell'
import { StatusBadge } from '@/components/app/domain'
import CompanyPicker from '@/components/app/CompanyPicker'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input, Label, Select } from '@/components/ui/input'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { EmptyState, Skeleton } from '@/components/ui/misc'
import { cn } from '@/lib/utils'

function initials(name = '') {
  return name.replace(/\b(ltd|limited|the)\b\.?/gi, '').trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
}

function AddCompanyDialog({ open, onOpenChange }) {
  const qc = useQueryClient()
  const [sel, setSel] = useState(null)
  const [tracked, setTracked] = useState(true)
  const create = useMutation({
    mutationFn: () => createCompany({ name: sel.name, ticker: sel.ticker, sector: sel.sector, is_tracked: tracked }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['companies'] })
      toast.success(`${sel.name} added`)
      setSel(null)
      onOpenChange(false)
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Could not add company'),
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogTitle>Add company</DialogTitle>
        <DialogDescription>Search across all NSE-listed companies.</DialogDescription>
        <div className="mt-5 space-y-4">
          <CompanyPicker value={sel} onChange={setSel} />
          <label className="flex items-center gap-2 text-[13px]">
            <input type="checkbox" checked={tracked} onChange={(e) => setTracked(e.target.checked)} className="size-4 accent-[hsl(var(--primary))]" />
            Track this company (watch for new filings)
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button disabled={!sel || create.isPending} onClick={() => create.mutate()}>Add company</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function Companies() {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [sector, setSector] = useState('all')
  const [view, setView] = useState('grid')
  const [adding, setAdding] = useState(false)
  const { data: companies = [], isLoading } = useQuery({ queryKey: ['companies'], queryFn: getCompanies })
  const { data: filings = [] } = useQuery({ queryKey: ['filings-all'], queryFn: () => getFilings() })

  const track = useMutation({
    mutationFn: (c) => updateCompany(c.id, { ...c, is_tracked: !c.is_tracked }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['companies'] }),
  })
  const remove = useMutation({
    mutationFn: (c) => deleteCompany(c.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['companies'] }); toast.success('Company removed') },
    onError: (e) => toast.error(e.response?.data?.detail || 'Delete failed'),
  })

  const byCompany = useMemo(() => {
    const m = {}
    for (const f of filings) (m[f.company_id] ||= []).push(f)
    for (const k in m) m[k].sort((a, b) => b.fiscal_year - a.fiscal_year)
    return m
  }, [filings])
  const sectors = ['all', ...new Set(companies.map((c) => c.sector).filter(Boolean))]
  const list = companies.filter(
    (c) => (sector === 'all' || c.sector === sector) &&
      (c.name.toLowerCase().includes(q.toLowerCase()) || (c.ticker || '').toLowerCase().includes(q.toLowerCase()))
  )

  const menu = (c) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" onClick={(e) => e.preventDefault()}><MoreHorizontal /></Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onSelect={() => track.mutate(c)}><Star /> {c.is_tracked ? 'Stop tracking' : 'Track company'}</DropdownMenuItem>
        <DropdownMenuItem className="text-danger focus:text-danger"
          onSelect={() => { if (window.confirm(`Remove ${c.name}?`)) remove.mutate(c) }}>
          <Trash2 className="!text-danger" /> Remove
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )

  return (
    <PageBody>
      <PageHeader
        title="Companies"
        description={`${companies.length} companies in your workspace`}
        actions={<Button onClick={() => setAdding(true)}><Plus /> Add company</Button>}
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or ticker" className="pl-9" />
        </div>
        <Select value={sector} onChange={(e) => setSector(e.target.value)} className="w-auto">
          {sectors.map((s) => <option key={s} value={s}>{s === 'all' ? 'All sectors' : s}</option>)}
        </Select>
        <div className="ml-auto flex rounded-md border p-0.5">
          {[['grid', LayoutGrid], ['list', List]].map(([v, I]) => (
            <button key={v} onClick={() => setView(v)} aria-label={`${v} view`}
              className={cn('rounded p-1.5 text-muted-foreground', view === v && 'bg-accent text-foreground')}>
              <I className="size-4" />
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-40" />)}</div>
      ) : !list.length ? (
        <EmptyState icon={Building2} title={companies.length ? 'No matches' : 'No companies yet'}
          description={companies.length ? 'Try a different search or sector.' : 'Add a company, or simply upload a report — the company is detected automatically.'}
          action={!companies.length && <Button onClick={() => setAdding(true)}><Plus /> Add company</Button>} />
      ) : view === 'grid' ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((c) => {
            const fs = byCompany[c.id] || []
            return (
              <Link key={c.id} to={`/app/companies/${c.id}`}>
                <Card className="group h-full p-5 transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lift">
                  <div className="flex items-start gap-3">
                    <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 text-[13px] font-semibold text-primary">
                      {initials(c.name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="truncate font-semibold group-hover:text-primary">{c.name}</p>
                        {c.is_tracked && <Star className="size-3.5 shrink-0 fill-warning text-warning" />}
                      </div>
                      <p className="text-[12px] text-muted-foreground">
                        {c.ticker && <span className="font-mono">{c.ticker}</span>}{c.ticker && c.sector && ' · '}{c.sector}
                      </p>
                    </div>
                    {menu(c)}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {fs.length ? fs.map((f) => (
                      <Badge key={f.id} variant={f.status === 'completed' ? 'secondary' : 'default'}>FY{f.fiscal_year}</Badge>
                    )) : <span className="text-[12px] text-muted-foreground">No reports yet</span>}
                  </div>
                  <p className="mt-3 text-[12px] text-muted-foreground">
                    {fs.length} report{fs.length === 1 ? '' : 's'} · {fs.reduce((s, f) => s + (f.page_count || 0), 0).toLocaleString('en-IN')} pages
                  </p>
                </Card>
              </Link>
            )
          })}
        </div>
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b bg-muted/40 text-left text-[12px] text-muted-foreground">
                <th className="px-5 py-2 font-medium">Company</th>
                <th className="px-3 py-2 font-medium">Sector</th>
                <th className="px-3 py-2 font-medium">Latest report</th>
                <th className="px-3 py-2 text-right font-medium">Reports</th>
                <th className="w-12" />
              </tr>
            </thead>
            <tbody>
              {list.map((c) => {
                const fs = byCompany[c.id] || []
                return (
                  <tr key={c.id} className="border-b last:border-0 hover:bg-accent/40">
                    <td className="px-5 py-2.5">
                      <Link to={`/app/companies/${c.id}`} className="font-medium hover:text-primary">{c.name}</Link>
                      {c.ticker && <span className="ml-2 font-mono text-[11px] text-muted-foreground">{c.ticker}</span>}
                    </td>
                    <td className="px-3 py-2.5 text-muted-foreground">{c.sector || '—'}</td>
                    <td className="px-3 py-2.5">{fs[0] ? <span className="flex items-center gap-2">FY{fs[0].fiscal_year} <StatusBadge status={fs[0].status} /></span> : '—'}</td>
                    <td className="tabular px-3 py-2.5 text-right">{fs.length}</td>
                    <td className="px-2">{menu(c)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}

      <AddCompanyDialog open={adding} onOpenChange={setAdding} />
    </PageBody>
  )
}
