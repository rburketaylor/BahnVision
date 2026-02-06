/**
 * Station Popup Component
 * BVV-styled with accent strip matching status and improved typography
 */

import type { StationStats } from '../../../types/gtfs'
import type { HeatmapPointLight } from '../../../types/heatmap'

interface StationPopupProps {
  station: HeatmapPointLight
  details?: StationStats
  isLoading: boolean
}

function getSeverityAccent(
  cancellationRate: number,
  delayRate: number
): 'red' | 'orange' | 'green' {
  const combinedRate = cancellationRate + delayRate
  if (combinedRate > 0.15) return 'red'
  if (combinedRate > 0.05) return 'orange'
  return 'green'
}

const accentColors = {
  red: 'bg-status-critical',
  orange: 'bg-status-warning',
  green: 'bg-status-healthy',
}

const textColors = {
  red: 'text-status-critical',
  orange: 'text-status-warning',
  green: 'text-status-healthy',
}

export function StationPopup({ station, details, isLoading }: StationPopupProps) {
  // Use station level intensity if details aren't loaded yet
  const initialAccent = station.i > 0.15 ? 'red' : station.i > 0.05 ? 'orange' : 'green'
  const accent = details
    ? getSeverityAccent(details.cancellation_rate, details.delay_rate)
    : initialAccent

  return (
    <div className="bv-map-popup min-h-[140px] flex flex-col justify-between">
      {/* Accent strip */}
      <div className={`absolute top-0 left-0 bottom-0 w-1 ${accentColors[accent]} rounded-l-lg`} />

      <div className="pl-3 pb-2">
        <h3 className="bv-map-popup__title text-h2 mb-1">{details?.station_name ?? station.n}</h3>

        {isLoading ? (
          <div className="mt-4 flex items-center gap-2 py-4">
            <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
            <span className="text-body text-muted">Loading details...</span>
          </div>
        ) : !details ? (
          <div className="mt-4 py-4">
            <p className="text-body text-muted">No real-time data available for this station.</p>
          </div>
        ) : (
          <>
            <div className="bv-map-popup__rows">
              <div className="bv-map-popup__row">
                <span className="bv-map-popup__label">Departures</span>
                <span className="bv-map-popup__value tabular-nums">
                  {details.total_departures.toLocaleString()}
                </span>
              </div>

              <div className="bv-map-popup__row">
                <span className="bv-map-popup__label">Cancellations</span>
                <span className={`bv-map-popup__value ${textColors.red} tabular-nums`}>
                  {details.cancelled_count} ({(details.cancellation_rate * 100).toFixed(1)}%)
                </span>
              </div>

              <div className="bv-map-popup__row">
                <span className="bv-map-popup__label">Delays (&gt;5 min)</span>
                <span className={`bv-map-popup__value ${textColors.orange} tabular-nums`}>
                  {details.delayed_count} ({(details.delay_rate * 100).toFixed(1)}%)
                </span>
              </div>
            </div>

            {details.by_transport.length > 0 && (
              <div className="mt-3 pt-3 border-t border-border/60">
                <p className="text-tiny text-muted mb-2 uppercase tracking-wide">
                  By Transport Type
                </p>
                {details.by_transport.map(t => (
                  <div key={t.transport_type} className="bv-map-popup__row">
                    <span className="bv-map-popup__label">{t.display_name}</span>
                    <span className="bv-map-popup__value tabular-nums">
                      {((t.cancellation_rate + t.delay_rate) * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <a className="bv-map-popup__link mt-auto" href={`/station/${station.id}`}>
        Full Details →
      </a>
    </div>
  )
}
