/**
 * MSW request handlers for API mocking
 */

import { http, HttpResponse } from 'msw'
import type {
  HealthResponse,
  Station,
  StationSearchResponse,
  DeparturesResponse,
  RoutePlanResponse,
  RoutePlan,
  RouteLeg,
  RouteStop,
} from '../../types/api'

const BASE_URL = 'http://localhost:8000'

export const handlers = [
  // Health endpoint
  http.get(`${BASE_URL}/api/v1/health`, () => {
    return HttpResponse.json<HealthResponse>({
      status: 'ok',
    })
  }),

  // Station search endpoint
  http.get(`${BASE_URL}/api/v1/mvg/stations/search`, ({ request }) => {
    const url = new URL(request.url)
    const query = url.searchParams.get('query') ?? ''
    const response: StationSearchResponse = {
      query,
      results: [
        {
          id: 'de:09162:6',
          name: 'Marienplatz',
          place: 'München',
          latitude: 48.137079,
          longitude: 11.575447,
        },
      ],
    }

    return HttpResponse.json(response, {
      headers: {
        'X-Cache-Status': 'hit',
      },
    })
  }),

  // Departures endpoint
  http.get(`${BASE_URL}/api/v1/mvg/departures`, () => {
    const response: DeparturesResponse = {
      station: {
        id: 'de:09162:6',
        name: 'Marienplatz',
        place: 'München',
        latitude: 48.137079,
        longitude: 11.575447,
      },
      departures: [
        {
          planned_time: new Date().toISOString(),
          realtime_time: new Date(Date.now() + 2 * 60000).toISOString(),
          delay_minutes: 2,
          platform: null,
          realtime: true,
          line: 'U3',
          destination: 'Moosach',
          transport_type: 'UBAHN',
          icon: 'mvg-u3',
          cancelled: false,
          messages: [],
        },
      ],
    }

    return HttpResponse.json(response, {
      headers: {
        'X-Cache-Status': 'hit',
      },
    })
  }),

  // Route planning endpoint
  http.get(`${BASE_URL}/api/v1/mvg/routes/plan`, () => {
    const now = new Date()
    const departureStop: RouteStop = {
      id: 'de:09162:6',
      name: 'Marienplatz',
      place: 'München',
      latitude: 48.137079,
      longitude: 11.575447,
      planned_time: now.toISOString(),
      realtime_time: now.toISOString(),
      platform: 'Gleis 1',
      transport_type: 'UBAHN',
      line: 'U3',
      destination: 'Sendlinger Tor',
      delay_minutes: 0,
      messages: [],
    }

    const arrivalStop: RouteStop = {
      id: 'de:09162:70',
      name: 'Sendlinger Tor',
      place: 'München',
      latitude: 48.134548,
      longitude: 11.566816,
      planned_time: new Date(now.getTime() + 15 * 60000).toISOString(),
      realtime_time: new Date(now.getTime() + 15 * 60000).toISOString(),
      platform: 'Gleis 2',
      transport_type: 'UBAHN',
      line: 'U3',
      destination: null,
      delay_minutes: 0,
      messages: [],
    }

    const leg: RouteLeg = {
      origin: departureStop,
      destination: arrivalStop,
      transport_type: 'UBAHN',
      line: 'U3',
      direction: 'Sendlinger Tor',
      duration_minutes: 15,
      distance_meters: 5400,
      intermediate_stops: [],
    }

    const plan: RoutePlan = {
      duration_minutes: 15,
      transfers: 0,
      departure: departureStop,
      arrival: arrivalStop,
      legs: [leg],
    }

    const originStation: Station = {
      id: 'de:09162:6',
      name: 'Marienplatz',
      place: 'München',
      latitude: 48.137079,
      longitude: 11.575447,
    }

    const destinationStation: Station = {
      id: 'de:09162:70',
      name: 'Sendlinger Tor',
      place: 'München',
      latitude: 48.134548,
      longitude: 11.566816,
    }

    const response: RoutePlanResponse = {
      origin: originStation,
      destination: destinationStation,
      plans: [plan],
    }

    return HttpResponse.json(response)
  }),
]
