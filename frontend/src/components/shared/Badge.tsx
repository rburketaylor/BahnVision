/**
 * Badge Component
 * Transport and status badges mapped to the shared token palette.
 */

import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Badge as UiBadge } from '../ui/badge'

export type BadgeVariant =
  | 'ubahn'
  | 'sbahn'
  | 'tram'
  | 'bus'
  | 'bahn'
  | 'primary'
  | 'success'
  | 'warning'
  | 'critical'
  | 'neutral'

export type BadgeShape = 'circular' | 'pill' | 'square'

export interface BadgeProps {
  children: ReactNode
  variant?: BadgeVariant
  shape?: BadgeShape
  className?: string
  small?: boolean
  outline?: boolean
}

const variantClasses: Record<BadgeVariant, { bg: string; text: string; border: string }> = {
  ubahn: { bg: 'bg-ubahn/90', text: 'text-white', border: 'border-ubahn/65' },
  sbahn: { bg: 'bg-sbahn/90', text: 'text-white', border: 'border-sbahn/65' },
  tram: { bg: 'bg-tram/90', text: 'text-white', border: 'border-tram/65' },
  bus: { bg: 'bg-bus/90', text: 'text-white', border: 'border-bus/65' },
  bahn: { bg: 'bg-surface-muted', text: 'text-foreground', border: 'border-border' },
  primary: { bg: 'bg-primary/12', text: 'text-primary', border: 'border-primary/35' },
  success: {
    bg: 'bg-status-healthy/14',
    text: 'text-status-healthy',
    border: 'border-status-healthy/35',
  },
  warning: {
    bg: 'bg-status-warning/14',
    text: 'text-status-warning',
    border: 'border-status-warning/40',
  },
  critical: {
    bg: 'bg-status-critical/14',
    text: 'text-status-critical',
    border: 'border-status-critical/40',
  },
  neutral: { bg: 'bg-surface-elevated', text: 'text-muted-foreground', border: 'border-border' },
}

const shapeClasses: Record<BadgeShape, string> = {
  circular: 'rounded-full aspect-square flex items-center justify-center',
  pill: 'rounded-md px-2.5',
  square: 'rounded-sm',
}

const sizeClasses: {
  normal: { circular: string; pill: string; square: string }
  small: { circular: string; pill: string; square: string }
} = {
  normal: {
    circular: 'w-8 h-8 text-xs',
    pill: 'py-1 text-[0.72rem]',
    square: 'px-2.5 py-1 text-[0.72rem]',
  },
  small: {
    circular: 'w-6 h-6 text-[0.62rem]',
    pill: 'py-0.5 text-[0.62rem]',
    square: 'px-2 py-0.5 text-[0.62rem]',
  },
}

export function Badge({
  children,
  variant = 'primary',
  shape = 'pill',
  className = '',
  small = false,
  outline = false,
}: BadgeProps) {
  const colors = variantClasses[variant]
  const shapeClass = shapeClasses[shape]
  const sizeClass = small ? sizeClasses.small[shape] : sizeClasses.normal[shape]

  const baseClasses = outline
    ? `bg-transparent border ${colors.border} ${colors.text}`
    : `border ${colors.border} ${colors.bg} ${colors.text}`

  return (
    <UiBadge
      variant="secondary"
      className={cn(
        'inline-flex items-center justify-center font-semibold uppercase tracking-[0.04em] border-0',
        shapeClass,
        sizeClass,
        baseClasses,
        className
      )}
    >
      {children}
    </UiBadge>
  )
}

export function TransportBadge({
  type,
  ...props
}: { type: string } & Omit<BadgeProps, 'variant' | 'children'>) {
  const variantMap: Record<string, BadgeVariant> = {
    UBAHN: 'ubahn',
    SBAHN: 'sbahn',
    TRAM: 'tram',
    BUS: 'bus',
    BAHN: 'bahn',
  }

  const labelMap: Record<string, string> = {
    UBAHN: 'U',
    SBAHN: 'S',
    TRAM: 'T',
    BUS: 'B',
    BAHN: 'R',
  }

  return (
    <Badge variant={variantMap[type] || 'neutral'} shape="circular" {...props}>
      {labelMap[type] || type.charAt(0)}
    </Badge>
  )
}
