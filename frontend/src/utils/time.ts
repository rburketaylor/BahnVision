/**
 * Time utility functions
 * Handles timezone conversion from UTC to Europe/Berlin
 */

const MUNICH_TIMEZONE = 'Europe/Berlin'

/**
 * Converts ISO 8601 UTC timestamp to Munich local time string
 */
export function toMunichTime(utcTime: string): Date {
  return new Date(utcTime)
}

/**
 * Formats time for display in HH:MM format in Munich timezone
 */
export function formatTime(utcTime: string): string {
  const date = toMunichTime(utcTime)
  return new Intl.DateTimeFormat('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: MUNICH_TIMEZONE,
  }).format(date)
}

/**
 * Formats date and time for display in Munich timezone
 */
export function formatDateTime(utcTime: string): string {
  const date = toMunichTime(utcTime)
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: MUNICH_TIMEZONE,
  }).format(date)
}

/**
 * Formats relative time (e.g., "in 5 minutes", "2 minutes ago")
 */
export function formatRelativeTime(utcTime: string): string {
  const date = toMunichTime(utcTime)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffMinutes = Math.round(diffMs / 60000)

  if (diffMinutes === 0) {
    return 'now'
  } else if (diffMinutes > 0) {
    return `in ${diffMinutes} min`
  } else {
    return `${Math.abs(diffMinutes)} min ago`
  }
}

/**
 * Converts Date to ISO 8601 UTC string for API requests
 */
export function toISOString(date: Date): string {
  return date.toISOString()
}
