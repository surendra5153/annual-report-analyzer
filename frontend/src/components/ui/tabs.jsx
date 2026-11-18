import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '@/lib/utils'

export const Tabs = TabsPrimitive.Root

export const TabsList = ({ className, ...p }) => (
  <TabsPrimitive.List
    className={cn('inline-flex h-9 items-center gap-1 rounded-lg bg-muted p-1 text-muted-foreground', className)}
    {...p}
  />
)

export const TabsTrigger = ({ className, ...p }) => (
  <TabsPrimitive.Trigger
    className={cn(
      'inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1 text-[13px] font-medium transition-all ' +
        'hover:text-foreground data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm [&_svg]:size-3.5',
      className
    )}
    {...p}
  />
)

/** Underline-style tabs for page-level navigation. */
export const TabsListLine = ({ className, ...p }) => (
  <TabsPrimitive.List className={cn('flex items-center gap-5 overflow-x-auto border-b', className)} {...p} />
)

export const TabsTriggerLine = ({ className, ...p }) => (
  <TabsPrimitive.Trigger
    className={cn(
      '-mb-px inline-flex items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent pb-2.5 pt-1 text-[13px] font-medium text-muted-foreground ' +
        'transition-colors hover:text-foreground data-[state=active]:border-primary data-[state=active]:text-foreground [&_svg]:size-3.5',
      className
    )}
    {...p}
  />
)

export const TabsContent = ({ className, ...p }) => (
  <TabsPrimitive.Content className={cn('mt-4 focus-visible:outline-none', className)} {...p} />
)
