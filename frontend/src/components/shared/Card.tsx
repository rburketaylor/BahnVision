/**
 * Card Component
 * Reusable card wrapper that keeps accent and spacing options.
 */

import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Card as UiCard } from '../ui/card'

export type CardAccent = 'blue' | 'green' | 'red' | 'orange' | 'none'

export interface CardProps {
  children: ReactNode
  accent?: CardAccent
  className?: string
  padding?: 'compact' | 'spacious'
  noHover?: boolean
}

const accentClasses: Record<CardAccent, string> = {
  blue: 'card-accent-blue',
  green: 'card-accent-green',
  red: 'card-accent-red',
  orange: 'card-accent-orange',
  none: '',
}

const paddingClasses: Record<'compact' | 'spacious', string> = {
  compact: 'p-4',
  spacious: 'p-5',
}

export function Card({
  children,
  accent = 'none',
  className = '',
  padding = 'compact',
  noHover = false,
}: CardProps) {
  return (
    <UiCard
      className={cn(
        'card-base',
        accentClasses[accent],
        paddingClasses[padding],
        noHover && 'hover:translate-y-0 hover:shadow-surface-1 hover:border-border',
        className
      )}
    >
      {children}
    </UiCard>
  )
}
