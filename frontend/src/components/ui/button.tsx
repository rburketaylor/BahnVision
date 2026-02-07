import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'btn-bvv inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md border border-transparent text-sm font-semibold tracking-[0.01em] transition-[color,background-color,border-color,box-shadow,transform] disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:h-4 [&_svg]:w-4 [&_svg]:shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
  {
    variants: {
      variant: {
        default:
          'bg-interactive text-primary-foreground shadow-surface-1 hover:bg-interactive-hover active:bg-interactive-active',
        secondary: 'border-border bg-surface-elevated text-foreground hover:bg-surface-muted',
        ghost: 'text-foreground hover:bg-surface-muted hover:text-foreground',
        outline:
          'border-border bg-card text-foreground hover:border-interactive/40 hover:bg-surface-elevated',
        destructive:
          'bg-destructive text-destructive-foreground shadow-surface-1 hover:bg-destructive/88 active:bg-destructive/76',
      },
      size: {
        default: 'h-10 px-4',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-11 px-6 text-sm',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
