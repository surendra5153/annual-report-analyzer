import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { Cpu, Menu, Monitor, Moon, PanelLeftClose, PanelLeftOpen, Plus, Search, Sun } from 'lucide-react'
import { getMlHealth } from '@/services/api'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Kbd } from '@/components/ui/misc'
import { Tooltip } from '@/components/ui/tooltip'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown'
import { Logo } from './Logo'
import { CommandMenu } from './CommandMenu'
import ErrorBoundary from './ErrorBoundary'
import { NAV } from './nav'

const COLLAPSE_KEY = 'finsight-sidebar-collapsed'

function SidebarNav({ collapsed, onNavigate }) {
  return (
    <nav className="flex flex-1 flex-col gap-5 px-3 py-4">
      {NAV.map((group) => (
        <div key={group.section}>
          {!collapsed && (
            <p className="mb-1.5 px-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">{group.section}</p>
          )}
          <ul className="space-y-0.5">
            {group.items.map((item) => (
              <li key={item.to}>
                <Tooltip content={collapsed ? item.label : null} side="right">
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex h-8 items-center gap-2.5 rounded-md px-2 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                        isActive && 'bg-accent text-foreground',
                        collapsed && 'justify-center px-0'
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && <span className="absolute -left-3 top-1.5 h-5 w-[3px] rounded-r bg-primary" />}
                        <item.icon className={cn('size-4 shrink-0', isActive && 'text-primary')} />
                        {!collapsed && item.label}
                      </>
                    )}
                  </NavLink>
                </Tooltip>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}

function ModelStatus({ collapsed }) {
  const { data, isError } = useQuery({ queryKey: ['ml-health'], queryFn: getMlHealth, refetchInterval: 30_000 })
  const up = data?.llm?.up && data?.llm?.model_available !== false
  const label = isError ? 'API offline' : !data ? 'Checking…' : up ? 'Local model online' : 'Model offline'
  const dot = (
    <span className="relative flex size-2">
      {up && <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-60" />}
      <span className={cn('relative inline-flex size-2 rounded-full', up ? 'bg-success' : isError ? 'bg-danger' : 'bg-warning')} />
    </span>
  )
  const detail = data?.llm?.model ? `${data.llm.model} via ${data.llm.provider} · embeddings ${data.embedding?.model}` : label
  if (collapsed) {
    return (
      <Tooltip content={detail} side="right">
        <div className="mx-auto mb-3 grid size-8 place-items-center rounded-md border">{dot}</div>
      </Tooltip>
    )
  }
  return (
    <Tooltip content={detail} side="right">
      <div className="mx-3 mb-3 flex items-center gap-2.5 rounded-lg border bg-background px-3 py-2.5">
        <Cpu className="size-4 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-medium leading-tight">{label}</p>
          <p className="truncate font-mono text-[10.5px] text-muted-foreground">{data?.llm?.model || '—'}</p>
        </div>
        {dot}
      </div>
    </Tooltip>
  )
}

function ThemeMenu() {
  const { theme, setTheme, resolved } = useTheme()
  const Icon = resolved === 'dark' ? Moon : Sun
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label="Theme">
          <Icon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {[['light', Sun, 'Light'], ['dark', Moon, 'Dark'], ['system', Monitor, 'System']].map(([t, I, l]) => (
          <DropdownMenuItem key={t} onSelect={() => setTheme(t)} className={cn(theme === t && 'font-medium text-primary')}>
            <I /> {l}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1' } catch { return false }
  })
  const [mobileOpen, setMobileOpen] = useState(false)
  const [cmdOpen, setCmdOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const toggle = () => {
    setCollapsed((c) => {
      try { localStorage.setItem(COLLAPSE_KEY, c ? '0' : '1') } catch { /* ignore */ }
      return !c
    })
  }

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'sticky top-0 hidden h-screen shrink-0 flex-col border-r bg-background transition-[width] duration-200 lg:flex',
          collapsed ? 'w-[60px]' : 'w-[232px]'
        )}
      >
        <div className={cn('flex h-14 items-center border-b', collapsed ? 'justify-center' : 'px-5')}>
          <Link to="/" aria-label="Home">
            <Logo collapsed={collapsed} />
          </Link>
        </div>
        <SidebarNav collapsed={collapsed} />
        <ModelStatus collapsed={collapsed} />
        <div className={cn('border-t p-2', collapsed && 'flex justify-center')}>
          <Button variant="ghost" size="sm" onClick={toggle} className={cn('text-muted-foreground', !collapsed && 'w-full justify-start')}>
            {collapsed ? <PanelLeftOpen /> : <><PanelLeftClose /> Collapse</>}
          </Button>
        </div>
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/40 lg:hidden"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r bg-background lg:hidden"
              initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            >
              <div className="flex h-14 items-center border-b px-5"><Logo /></div>
              <SidebarNav onNavigate={() => setMobileOpen(false)} />
              <ModelStatus />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-md lg:px-6">
          <Button variant="ghost" size="icon-sm" className="lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open menu">
            <Menu />
          </Button>
          <button
            onClick={() => setCmdOpen(true)}
            className="flex h-8 w-full max-w-sm items-center gap-2 rounded-md border bg-muted/40 px-3 text-[13px] text-muted-foreground transition-colors hover:bg-muted"
          >
            <Search className="size-3.5" />
            <span className="flex-1 text-left">Search companies, reports…</span>
            <Kbd className="hidden sm:inline-flex">Ctrl K</Kbd>
          </button>
          <div className="ml-auto flex items-center gap-1">
            <ThemeMenu />
            <Button asChild size="sm" className="ml-1">
              <Link to="/app/upload"><Plus /> <span className="hidden sm:inline">New report</span></Link>
            </Button>
          </div>
        </header>

        <main className="flex-1">
          <ErrorBoundary resetKey={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>

      <CommandMenu open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  )
}

/** Standard page header used by every app page. */
export function PageHeader({ title, description, actions, eyebrow, className }) {
  return (
    <div className={cn('flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between', className)}>
      <div className="min-w-0">
        {eyebrow && <div className="mb-1.5 text-[12px] font-medium text-muted-foreground">{eyebrow}</div>}
        <h1 className="truncate text-[22px] font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-[13.5px] text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}

export const PageBody = ({ className, ...p }) => (
  <div className={cn('mx-auto w-full max-w-[1320px] animate-fade-up space-y-6 px-4 py-6 lg:px-8 lg:py-8', className)} {...p} />
)
