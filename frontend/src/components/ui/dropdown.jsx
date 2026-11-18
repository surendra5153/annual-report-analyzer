import * as DM from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'

export const DropdownMenu = DM.Root
export const DropdownMenuTrigger = DM.Trigger

export const DropdownMenuContent = ({ className, align = 'end', ...p }) => (
  <DM.Portal>
    <DM.Content
      align={align}
      sideOffset={6}
      className={cn(
        'z-50 min-w-[10rem] rounded-lg border bg-popover p-1 text-popover-foreground shadow-lift animate-in fade-in-0 zoom-in-95',
        className
      )}
      {...p}
    />
  </DM.Portal>
)

export const DropdownMenuItem = ({ className, ...p }) => (
  <DM.Item
    className={cn(
      'flex cursor-default select-none items-center gap-2 rounded-md px-2 py-1.5 text-[13px] outline-none ' +
        'focus:bg-accent data-[disabled]:opacity-50 [&_svg]:size-4 [&_svg]:text-muted-foreground',
      className
    )}
    {...p}
  />
)

export const DropdownMenuLabel = ({ className, ...p }) => (
  <DM.Label className={cn('px-2 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground', className)} {...p} />
)

export const DropdownMenuSeparator = ({ className, ...p }) => (
  <DM.Separator className={cn('-mx-1 my-1 h-px bg-border', className)} {...p} />
)
