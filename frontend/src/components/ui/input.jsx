import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

const field =
  'flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm transition-colors ' +
  'placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 ' +
  'focus-visible:border-ring focus-visible:ring-offset-0 disabled:opacity-50'

export const Input = forwardRef(({ className, ...p }, ref) => <input ref={ref} className={cn(field, className)} {...p} />)
Input.displayName = 'Input'

export const Textarea = forwardRef(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(field, 'h-auto min-h-[44px] resize-none py-2.5', className)} {...p} />
))
Textarea.displayName = 'Textarea'

export const Label = ({ className, ...p }) => (
  <label className={cn('text-[13px] font-medium leading-none', className)} {...p} />
)

export const Select = forwardRef(({ className, children, ...p }, ref) => (
  <select ref={ref} className={cn(field, 'px-2.5', className)} {...p}>
    {children}
  </select>
))
Select.displayName = 'Select'
