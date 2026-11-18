import { BRAND } from '@/lib/brand'
import { cn } from '@/lib/utils'

export function LogoMark({ className }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('size-7', className)} aria-hidden>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path d="M9 21.5V14M14.5 21.5V10M20 21.5v-5M25 9l-5.2 5.2-3-3L9 19" fill="none"
        className="stroke-primary-foreground" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Logo({ className, collapsed }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark />
      {!collapsed && <span className="text-[15px] font-semibold tracking-tight">{BRAND.name}</span>}
    </span>
  )
}
