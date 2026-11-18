import { cn } from '@/lib/utils'

export const Card = ({ className, ...p }) => (
  <div className={cn('rounded-lg border bg-card text-card-foreground shadow-card', className)} {...p} />
)
export const CardHeader = ({ className, ...p }) => (
  <div className={cn('flex items-start justify-between gap-4 p-5 pb-3', className)} {...p} />
)
export const CardTitle = ({ className, ...p }) => (
  <h3 className={cn('text-[15px] font-semibold leading-none tracking-tight', className)} {...p} />
)
export const CardDescription = ({ className, ...p }) => (
  <p className={cn('mt-1.5 text-[13px] text-muted-foreground', className)} {...p} />
)
export const CardContent = ({ className, ...p }) => <div className={cn('p-5 pt-0', className)} {...p} />
export const CardFooter = ({ className, ...p }) => (
  <div className={cn('flex items-center border-t px-5 py-3', className)} {...p} />
)
