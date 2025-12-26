/**
 * Time utility functions
 * Handles timezone conversion from UTC to Europe/Berlin
 */

const MUNICH_TIMEZONE = 'Europe/Berlin'

/**
 * Formats time for display in HH:MM format in Munich timezone
 */
export function formatTime(utcTime: string | null | undefined, use24Hour = true): string {
  if (!utcTime) return '--:--'

  const date = new Date(utcTime)
  if (Number.isNaN(date.getTime())) {
    return '--:--'
  }

  return new Intl.DateTimeFormat('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: !use24Hour,
    timeZone: MUNICH_TIMEZONE,
  }).format(date)
}
