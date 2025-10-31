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

  it('should search stations', async () => {
    const response = await apiClient.searchStations({ q: 'Marienplatz' })
    expect(response.data.results).toHaveLength(1)
    expect(response.data.results[0].name).toBe('Marienplatz')
    expect(response.cacheStatus).toBe('hit')
  })

  it('should fetch departures', async () => {
    const response = await apiClient.getDepartures({ station: 'de:09162:6' })
    expect(response.data.departures).toHaveLength(1)
    expect(response.data.station.name).toBe('Marienplatz')
  })
})
