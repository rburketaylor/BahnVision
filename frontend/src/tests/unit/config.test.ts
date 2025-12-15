/**
 * Tests for config module
 * Target: lib/config.ts (0% mutation score → 40%+)
 *
 * Note: Testing config is tricky because import.meta.env is evaluated at import time.
 * These tests verify the config object structure and values.
 */

import { describe, it, expect } from 'vitest'
import { config } from '../../lib/config'

describe('config', () => {
  describe('structure', () => {
    it('exports a config object', () => {
      expect(config).toBeDefined()
      expect(typeof config).toBe('object')
    })

    it('has all required properties', () => {
      expect(config).toHaveProperty('apiBaseUrl')
      expect(config).toHaveProperty('sentryDsn')
      expect(config).toHaveProperty('enableDebugLogs')
      expect(config).toHaveProperty('mapTileUrl')
      expect(config).toHaveProperty('mapAttribution')
      expect(config).toHaveProperty('environment')
    })
  })

  describe('apiBaseUrl', () => {
    it('is a string', () => {
      expect(typeof config.apiBaseUrl).toBe('string')
    })

    it('is not empty', () => {
      expect(config.apiBaseUrl.length).toBeGreaterThan(0)
    })

    it('starts with http', () => {
      expect(config.apiBaseUrl).toMatch(/^https?:\/\//)
    })

    it('has a default value when env var is not set', () => {
      // In test environment, should default to localhost
      expect(config.apiBaseUrl).toContain('localhost')
    })
  })

  describe('sentryDsn', () => {
    it('is undefined or a string', () => {
      expect(config.sentryDsn === undefined || typeof config.sentryDsn === 'string').toBe(true)
    })
  })

  describe('enableDebugLogs', () => {
    it('is a boolean', () => {
      expect(typeof config.enableDebugLogs).toBe('boolean')
    })
  })

  describe('mapTileUrl', () => {
    it('is a string', () => {
      expect(typeof config.mapTileUrl).toBe('string')
    })

    it('contains tile URL placeholders', () => {
      // Leaflet tile URLs should have {s}, {z}, {x}, {y} placeholders
      expect(config.mapTileUrl).toContain('{z}')
      expect(config.mapTileUrl).toContain('{x}')
      expect(config.mapTileUrl).toContain('{y}')
    })

    it('has default OpenStreetMap URL', () => {
      expect(config.mapTileUrl).toContain('openstreetmap')
    })
  })

  describe('mapAttribution', () => {
    it('is a string', () => {
      expect(typeof config.mapAttribution).toBe('string')
    })

    it('contains OpenStreetMap attribution', () => {
      expect(config.mapAttribution).toContain('OpenStreetMap')
    })
  })

  describe('environment', () => {
    it('is one of the allowed values', () => {
      const allowedValues = ['development', 'production', 'test']
      expect(allowedValues).toContain(config.environment)
    })

    it('is "test" in test environment', () => {
      // When running Vitest, MODE should be 'test'
      expect(config.environment).toBe('test')
    })
  })
})
