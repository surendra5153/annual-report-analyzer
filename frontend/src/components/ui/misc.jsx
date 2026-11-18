import * as ProgressPrimitive from '@radix-ui/react-progress'
import { cn } from '@/lib/utils'

export const Skeleton = ({ className, ...p }) => (
  <div className={cn('relative overflow-hidden rounded-md bg-muted', className)} {...p}>
    <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-foreground/[.05] to-transparent" />
  </div>
)

export const Progress = ({ value = 0, className, indicatorClassName }) => (
  <ProgressPrimitive.Root className={cn('relative h-1.5 w-full overflow-hidden rounded-full bg-muted', className)} value={value}>
    <ProgressPrimitive.Indicator
      className={cn('h-full bg-primary transition-transform duration-500 ease-out', indicatorClassName)}
      style={{ transform: `translateX(-${100 - Math.min(100, Math.max(0, value))}%)` }}
    />
  </ProgressPrimitive.Root>
)

export const Separator = ({ className, vertical }) => (
  <div className={cn('shrink-0 bg-border', vertical ? 'h-full w-px' : 'h-px w-full', className)} />
)

export const Kbd = ({ className, ...p }) => (
  <kbd
    className={cn(
      'pointer-events-none inline-flex h-5 select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground',
      className
    )}
    {...p}
  />
)

export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-lg border border-dashed px-6 py-12 text-center', className)}>
      {Icon && (
        <div className="mb-3 grid size-10 place-items-center rounded-lg border bg-background shadow-sm">
          <Icon className="size-5 text-muted-foreground" />
        </div>
      )}
      <p className="font-medium">{title}</p>
      {description && <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/** Small "label: value" stat with optional delta, used in tiles. */
export function Delta({ value, className, invert = false }) {
  if (value === null || value === undefined || Number.isNaN(value)) return null
  const good = invert ? value < 0 : value >= 0
  return (
    <span className={cn('tabular text-[12px] font-medium', good ? 'text-success' : 'text-danger', className)}>
      {value >= 0 ? '▲' : '▼'} {Math.abs(value).toFixed(1)}%
    </span>
  )
}
