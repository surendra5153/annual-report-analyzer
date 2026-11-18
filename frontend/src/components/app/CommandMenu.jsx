import { useEffect } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { Building2, FileText, Moon, Search, Sun, Monitor, Upload } from 'lucide-react'
import { getCompanies, getFilings } from '@/services/api'
import { useTheme } from '@/lib/theme'
import { NAV } from './nav'

const groupCls =
  '[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[11px] ' +
  '[&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-muted-foreground'
const itemCls =
  'flex cursor-default select-none items-center gap-2.5 rounded-md px-2 py-2 text-[13px] data-[selected=true]:bg-accent [&_svg]:size-4 [&_svg]:text-muted-foreground'

export function CommandMenu({ open, onOpenChange }) {
  const navigate = useNavigate()
  const { setTheme } = useTheme()
  const { data: companies = [] } = useQuery({ queryKey: ['companies'], queryFn: getCompanies, enabled: open })
  const { data: filings = [] } = useQuery({ queryKey: ['filings-all'], queryFn: () => getFilings(), enabled: open })

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        onOpenChange(!open)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  const go = (path) => {
    onOpenChange(false)
    navigate(path)
  }
  const companyName = Object.fromEntries(companies.map((c) => [c.id, c.name]))

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content className="fixed left-1/2 top-[14vh] z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border bg-popover shadow-lift data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <DialogPrimitive.Title className="sr-only">Command menu</DialogPrimitive.Title>
          <Command loop>
            <div className="flex items-center gap-2 border-b px-3">
              <Search className="size-4 text-muted-foreground" />
              <Command.Input
                autoFocus
                placeholder="Search companies, reports, pages…"
                className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
            </div>
            <Command.List className="max-h-[360px] overflow-y-auto p-2">
              <Command.Empty className="py-8 text-center text-[13px] text-muted-foreground">No results.</Command.Empty>

              <Command.Group heading="Navigate" className={groupCls}>
                {NAV.flatMap((s) => s.items).map((item) => (
                  <Command.Item key={item.to} value={`go ${item.label}`} onSelect={() => go(item.to)} className={itemCls}>
                    <item.icon /> {item.label}
                  </Command.Item>
                ))}
                <Command.Item value="upload new report" onSelect={() => go('/app/upload')} className={itemCls}>
                  <Upload /> Upload a new report
                </Command.Item>
              </Command.Group>

              {companies.length > 0 && (
                <Command.Group heading="Companies" className={groupCls}>
                  {companies.map((c) => (
                    <Command.Item key={c.id} value={`company ${c.name} ${c.ticker || ''}`} onSelect={() => go(`/app/companies/${c.id}`)} className={itemCls}>
                      <Building2 /> {c.name}
                      {c.ticker && <span className="ml-auto font-mono text-[11px] text-muted-foreground">{c.ticker}</span>}
                    </Command.Item>
                  ))}
                </Command.Group>
              )}

              {filings.length > 0 && (
                <Command.Group heading="Reports" className={groupCls}>
                  {filings.map((f) => (
                    <Command.Item key={f.id} value={`report ${companyName[f.company_id] || ''} ${f.fiscal_year} ${f.file_name}`} onSelect={() => go(`/app/filings/${f.id}`)} className={itemCls}>
                      <FileText /> {companyName[f.company_id] || f.file_name}
                      <span className="ml-auto text-[11px] text-muted-foreground">FY{f.fiscal_year}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}

              <Command.Group heading="Theme" className={groupCls}>
                {[['light', Sun], ['dark', Moon], ['system', Monitor]].map(([t, Icon]) => (
                  <Command.Item key={t} value={`theme ${t}`} onSelect={() => { setTheme(t); onOpenChange(false) }} className={itemCls}>
                    <Icon /> Switch to {t} theme
                  </Command.Item>
                ))}
              </Command.Group>
            </Command.List>
          </Command>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
