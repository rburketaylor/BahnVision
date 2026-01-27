/**
 * Card Component
 * Reusable card with BVV-style left accent border and hover effects
 */

import { type ReactNode } from 'react'

export type CardAccent = 'blue' | 'green' | 'red' | 'orange' | 'none'

export interface CardProps {
  /** Card content */
  children: ReactNode
  /** Accent color for left border */
  accent?: CardAccent
  /** Additional CSS classes */
  className?: string
  /** Padding variant */
  padding?: 'compact' | 'spacious'
  /** Disable hover lift effect */
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
  const hoverClass = noHover ? '' : 'card-base'

  return (
    <div
      className={`card-base ${accentClasses[accent]} ${paddingClasses[padding]} ${hoverClass} ${className}`.trim()}
    >
      {children}
    </div>
  )
}
