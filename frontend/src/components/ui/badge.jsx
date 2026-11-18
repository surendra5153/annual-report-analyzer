import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none whitespace-nowrap [&_svg]:size-3',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary/10 text-primary',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        outline: 'text-muted-foreground',
        success: 'border-transparent bg-success/15 text-success',
        warning: 'border-transparent bg-warning/15 text-warning',
        danger: 'border-transparent bg-danger/15 text-danger',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)

export const Badge = ({ className, variant, ...p }) => <span className={cn(badgeVariants({ variant }), className)} {...p} />

const SEVERITY = { critical: 'danger', high: 'danger', medium: 'warning', low: 'secondary' }
export const SeverityBadge = ({ severity }) => (
  <Badge variant={SEVERITY[severity] || 'secondary'} className="capitalize">
    {severity}
  </Badge>
)
