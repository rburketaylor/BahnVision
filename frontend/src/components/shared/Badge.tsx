/**
 * Badge Component
 * BVV-style transport mode badges with circular icons or pill shapes
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
  /** Badge content */
  children: ReactNode
  /** Transport type or status variant */
  variant?: BadgeVariant
  /** Badge shape */
  shape?: BadgeShape
  /** Additional CSS classes */
  className?: string
  /** Small size */
  small?: boolean
  /** Show as outline/hollow */
  outline?: boolean
}

const variantClasses: Record<BadgeVariant, { bg: string; text: string; border: string }> = {
  ubahn: { bg: 'bg-ubahn', text: 'text-white', border: 'border-ubahn' },
  sbahn: { bg: 'bg-sbahn', text: 'text-white', border: 'border-sbahn' },
  tram: { bg: 'bg-tram', text: 'text-white', border: 'border-tram' },
  bus: { bg: 'bg-bus', text: 'text-white', border: 'border-bus' },
  bahn: { bg: 'bg-gray-600', text: 'text-white', border: 'border-gray-600' },
  primary: { bg: 'bg-primary', text: 'text-white', border: 'border-primary' },
  success: { bg: 'bg-status-healthy', text: 'text-white', border: 'border-status-healthy' },
  warning: { bg: 'bg-status-warning', text: 'text-white', border: 'border-status-warning' },
  critical: { bg: 'bg-status-critical', text: 'text-white', border: 'border-status-critical' },
  neutral: { bg: 'bg-muted', text: 'text-foreground', border: 'border-muted' },
}

const shapeClasses: Record<BadgeShape, string> = {
  circular: 'rounded-full aspect-square flex items-center justify-center',
  pill: 'rounded-full px-2.5',
  square: 'rounded-md',
}

const sizeClasses: {
  normal: { circular: string; pill: string; square: string }
  small: { circular: string; pill: string; square: string }
} = {
  normal: {
    circular: 'w-8 h-8',
    pill: 'py-1 text-xs',
    square: 'px-2.5 py-1 text-xs',
  },
  small: {
    circular: 'w-6 h-6',
    pill: 'py-0.5 text-[10px]',
    square: 'px-2 py-0.5 text-[10px]',
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
    : `${colors.bg} ${colors.text}`

  return (
    <UiBadge
      variant="secondary"
      className={cn(
        'inline-flex items-center justify-center font-medium btn-bvv border-0',
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

/** Transport type badges with predefined labels */
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
