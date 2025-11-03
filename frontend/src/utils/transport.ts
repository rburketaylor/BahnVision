/**
 * Transport type utilities
 * Provides colors, labels, and icons for different transport types
 */

import type { TransportType } from '../types/api'

export const TRANSPORT_COLORS: Record<TransportType, string> = {
  BAHN: '#00558C',
  SBAHN: '#00AB4E',
  UBAHN: '#0065AE',
  TRAM: '#D60F26',
  BUS: '#00558C',
  REGIONAL_BUS: '#00558C',
  SEV: '#00558C',
  SCHIFF: '#00558C',
}

export const TRANSPORT_LABELS: Record<TransportType, string> = {
  BAHN: 'Bahn',
  SBAHN: 'S-Bahn',
  UBAHN: 'U-Bahn',
  TRAM: 'Tram',
  BUS: 'Bus',
  REGIONAL_BUS: 'Regional Bus',
  SEV: 'SEV',
  SCHIFF: 'Schiff',
}

export function getTransportColor(type: TransportType): string {
  return TRANSPORT_COLORS[type]
}

export function getTransportLabel(type: TransportType): string {
  return TRANSPORT_LABELS[type]
}
