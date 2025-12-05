/**
 * API client unit tests
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest'
import { apiClient } from '../../services/api'
import { server } from '../mocks/server'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('API Client', () => {
  it('should fetch health status', async () => {
    const response = await apiClient.getHealth()
    expect(response.data.status).toBe('ok')
  })

  it('should search stops', async () => {
    const response = await apiClient.searchStops({ query: 'Marienplatz' })
    expect(response.data.results).toHaveLength(1)
    expect(response.data.results[0].name).toBe('Marienplatz')
    expect(response.cacheStatus).toBe('hit')
  })

  it('should fetch departures', async () => {
    const response = await apiClient.getDepartures({ stop_id: 'de:09162:6' })
    expect(response.data.departures).toHaveLength(2) // Our mock now returns 2 departures
    expect(response.data.stop.name).toBe('Marienplatz')
  })
})
