/**
 * Transport type utilities
 * Provides colors, labels, and icons for different transport types
 */

import type { TransportType } from '../types/api'

export const TRANSPORT_COLORS: Record<TransportType, string> = {
  UBAHN: '#0065AE', // U-Bahn blue
  SBAHN: '#00AB4E', // S-Bahn green
  TRAM: '#D60F26', // Tram red
  BUS: '#00558C', // Bus dark blue
  REGIONAL: '#00558C', // Regional services dark blue
}

export const TRANSPORT_LABELS: Record<TransportType, string> = {
  UBAHN: 'U-Bahn',
  SBAHN: 'S-Bahn',
  TRAM: 'Tram',
  BUS: 'Bus',
  REGIONAL: 'Regional',
}

export function getTransportColor(type: TransportType): string {
  return TRANSPORT_COLORS[type]
}

export function getTransportLabel(type: TransportType): string {
  return TRANSPORT_LABELS[type]
}
