import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center border px-2.5 py-1 text-[0.72rem] font-semibold uppercase tracking-[0.045em] transition-colors',
  {
    variants: {
      variant: {
        default: 'border-primary/30 bg-primary/12 text-primary',
        secondary: 'border-border bg-surface-elevated text-foreground',
        outline: 'border-border bg-transparent text-foreground',
        destructive: 'border-destructive/35 bg-destructive/10 text-destructive',
      },
      shape: {
        default: 'rounded-md',
        pill: 'rounded-full',
      },
    },
    defaultVariants: {
      variant: 'default',
      shape: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, shape, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, shape }), className)} {...props} />
}

export { Badge, badgeVariants }
