/**
 * MSW request handlers for API mocking
 * 
 * Updated to use Transit API (GTFS) endpoints.
 */

import { http, HttpResponse } from 'msw'
import type { HealthResponse } from '../../types/api'
import type { 
  TransitStop, 
  TransitStopSearchResponse,
  TransitDeparturesResponse,
  TransitDeparture,
} from '../../types/gtfs'
import type { HeatmapResponse } from '../../types/heatmap'

const BASE_URL = 'http://localhost:8000'

// Sample stops for testing
const sampleStops: TransitStop[] = [
  {
    id: 'de:09162:6',
    name: 'Marienplatz',
    latitude: 48.137079,
    longitude: 11.575447,
    zone_id: 'M',
    wheelchair_boarding: 1,
  },
  {
    id: 'de:09162:70',
    name: 'Sendlinger Tor',
    latitude: 48.134548,
    longitude: 11.566816,
    zone_id: 'M',
    wheelchair_boarding: 1,
  },
  {
    id: 'de:09162:1',
    name: 'Hauptbahnhof',
    latitude: 48.14,
    longitude: 11.558,
    zone_id: 'M',
    wheelchair_boarding: 1,
  },
]

// Sample departures for testing
function createSampleDepartures(stopId: string, stopName: string): TransitDeparture[] {
  const now = new Date()
  return [
    {
      trip_id: 'trip_1',
      route_id: 'U3',
      route_short_name: 'U3',
      route_long_name: 'U-Bahn Line 3',
      headsign: 'Moosach',
      stop_id: stopId,
      stop_name: stopName,
      scheduled_departure: now.toISOString(),
      scheduled_arrival: null,
      realtime_departure: new Date(now.getTime() + 2 * 60000).toISOString(),
      realtime_arrival: null,
      departure_delay_seconds: 120,
      arrival_delay_seconds: null,
      schedule_relationship: 'SCHEDULED',
      vehicle_id: null,
      alerts: [],
    },
    {
      trip_id: 'trip_2',
      route_id: 'S1',
      route_short_name: 'S1',
      route_long_name: 'S-Bahn Line 1',
      headsign: 'Flughafen',
      stop_id: stopId,
      stop_name: stopName,
      scheduled_departure: new Date(now.getTime() + 5 * 60000).toISOString(),
      scheduled_arrival: null,
      realtime_departure: new Date(now.getTime() + 5 * 60000).toISOString(),
      realtime_arrival: null,
      departure_delay_seconds: 0,
      arrival_delay_seconds: null,
      schedule_relationship: 'SCHEDULED',
      vehicle_id: null,
      alerts: [],
    },
  ]
}

export const handlers = [
  // Health endpoint
  http.get(`${BASE_URL}/api/v1/health`, () => {
    return HttpResponse.json<HealthResponse>({
      status: 'ok',
    })
  }),

  // Transit stop search endpoint
  http.get(`${BASE_URL}/api/v1/transit/stops/search`, ({ request }) => {
    const url = new URL(request.url)
    const query = url.searchParams.get('query')?.toLowerCase() ?? ''
    
    const filteredStops = sampleStops.filter(stop => 
      stop.name.toLowerCase().includes(query)
    )
    
    const response: TransitStopSearchResponse = {
      query,
      results: filteredStops,
    }

    return HttpResponse.json(response, {
      headers: {
        'X-Cache-Status': 'hit',
      },
    })
  }),

  // Transit departures endpoint
  http.get(`${BASE_URL}/api/v1/transit/departures`, ({ request }) => {
    const url = new URL(request.url)
    const stopId = url.searchParams.get('stop_id') ?? 'de:09162:6'
    
    const stop = sampleStops.find(s => s.id === stopId) ?? sampleStops[0]
    
    const response: TransitDeparturesResponse = {
      stop,
      departures: createSampleDepartures(stop.id, stop.name),
      realtime_available: true,
    }

    return HttpResponse.json(response, {
      headers: {
        'X-Cache-Status': 'hit',
      },
    })
  }),

  // Get single stop endpoint
  http.get(`${BASE_URL}/api/v1/transit/stops/:stopId`, ({ params }) => {
    const stopId = params.stopId as string
    const stop = sampleStops.find(s => s.id === stopId)
    
    if (!stop) {
      return HttpResponse.json({ detail: 'Stop not found' }, { status: 404 })
    }
    
    return HttpResponse.json(stop)
  }),

  // Heatmap cancellations endpoint
  http.get(`${BASE_URL}/api/v1/heatmap/cancellations`, () => {
    const now = new Date()
    const from = new Date(now.getTime() - 24 * 60 * 60 * 1000)

    const response: HeatmapResponse = {
      time_range: {
        from: from.toISOString(),
        to: now.toISOString(),
      },
      data_points: [
        {
          station_id: 'de:09162:6',
          station_name: 'Marienplatz',
          latitude: 48.137079,
          longitude: 11.575447,
          total_departures: 1250,
          cancelled_count: 45,
          cancellation_rate: 0.036,
          by_transport: {
            UBAHN: { total: 500, cancelled: 20 },
            SBAHN: { total: 750, cancelled: 25 },
          },
        },
        {
          station_id: 'de:09162:1',
          station_name: 'Hauptbahnhof',
          latitude: 48.14,
          longitude: 11.558,
          total_departures: 2000,
          cancelled_count: 80,
          cancellation_rate: 0.04,
          by_transport: {
            UBAHN: { total: 800, cancelled: 32 },
            SBAHN: { total: 1200, cancelled: 48 },
          },
        },
      ],
      summary: {
        total_stations: 2,
        total_departures: 3250,
        total_cancellations: 125,
        overall_cancellation_rate: 0.038,
        most_affected_station: 'Hauptbahnhof',
        most_affected_line: 'S-Bahn',
      },
    }

    return HttpResponse.json(response, {
      headers: {
        'X-Cache-Status': 'miss',
      },
    })
  }),
]
