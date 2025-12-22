import { describe, it, expect, beforeEach, vi } from 'vitest'

import { transitApiClient } from '../../services/endpoints/transitApi'
import { httpClient } from '../../services/httpClient'

vi.mock('../../services/httpClient', () => ({
  httpClient: {
    baseUrl: 'https://api.example.test',
    request: vi.fn(),
  },
}))

const mockRequest = vi.mocked(httpClient.request)

describe('transitApiClient', () => {
  beforeEach(() => {
    mockRequest.mockReset()
    mockRequest.mockResolvedValue({} as never)
  })

  it('encodes stop IDs in getStop', async () => {
    await transitApiClient.getStop('a/b')
    expect(mockRequest).toHaveBeenCalledWith('/api/v1/transit/stops/a%2Fb', { timeout: 5000 })
  })

  it('builds query strings including arrays', async () => {
    await transitApiClient.searchStops({ query: ['A', 'B'] as unknown as string })

    const [url] = mockRequest.mock.calls[0] ?? []
    expect(url).toContain('/api/v1/transit/stops/search?')
    expect(url).toContain('query=A')
    expect(url).toContain('query=B')
  })

  it('includes query params for getNearbyStops', async () => {
    await transitApiClient.getNearbyStops({ latitude: 48.1, longitude: 11.5, limit: 5 })
    expect(mockRequest).toHaveBeenCalledWith(
      '/api/v1/transit/stops/nearby?latitude=48.1&longitude=11.5&limit=5',
      { timeout: 8000 }
    )
  })

  it('builds station stats URLs with stop_id and query params', async () => {
    await transitApiClient.getStationStats({ stop_id: 'stop:1', time_range: '24h' })
    expect(mockRequest).toHaveBeenCalledWith(
      '/api/v1/transit/stops/stop%3A1/stats?time_range=24h',
      { timeout: 10000 }
    )
  })

  it('builds station trends URLs with stop_id and query params', async () => {
    await transitApiClient.getStationTrends({
      stop_id: 'stop:1',
      time_range: '24h',
      granularity: 'daily',
    })
    expect(mockRequest).toHaveBeenCalledWith(
      '/api/v1/transit/stops/stop%3A1/trends?time_range=24h&granularity=daily',
      { timeout: 10000 }
    )
  })
})
