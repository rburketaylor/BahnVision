/**
 * Tests for GTFS type helper functions
 * Target: types/gtfs.ts helper functions
 */

import { describe, it, expect } from 'vitest'
import {
    GtfsRouteType,
    getDelayMinutes,
    isDelayed,
    getEffectiveDepartureTime,
    getRouteTypeName,
    getRouteTypeFromString,
    type TransitDeparture,
} from '../../types/gtfs'

describe('GTFS helper functions', () => {
    describe('getDelayMinutes', () => {
        it('returns 0 for null delay', () => {
            expect(getDelayMinutes(null)).toBe(0)
        })

        it('returns 0 for 0 seconds delay', () => {
            expect(getDelayMinutes(0)).toBe(0)
        })

        it('converts positive seconds to minutes', () => {
            expect(getDelayMinutes(60)).toBe(1) // 1 minute
            expect(getDelayMinutes(120)).toBe(2) // 2 minutes
            expect(getDelayMinutes(300)).toBe(5) // 5 minutes
            expect(getDelayMinutes(600)).toBe(10) // 10 minutes
        })

        it('rounds to nearest minute', () => {
            expect(getDelayMinutes(30)).toBe(1) // 0.5 minutes rounds to 1
            expect(getDelayMinutes(89)).toBe(1) // 1.48 minutes rounds to 1
            expect(getDelayMinutes(90)).toBe(2) // 1.5 minutes rounds to 2
            expect(getDelayMinutes(150)).toBe(3) // 2.5 minutes rounds to 3
        })

        it('handles negative delays (early arrival)', () => {
            expect(getDelayMinutes(-60)).toBe(-1)
            expect(getDelayMinutes(-120)).toBe(-2)
            // Note: Math.round(-0.5) = -0 in JavaScript
            expect(getDelayMinutes(-30)).toBe(-0)
        })
    })

    describe('isDelayed', () => {
        const createDeparture = (delay: number | null): TransitDeparture => ({
            trip_id: 'trip1',
            route_id: 'route1',
            route_short_name: 'U1',
            route_long_name: 'U-Bahn 1',
            headsign: 'Test Destination',
            stop_id: 'stop1',
            stop_name: 'Test Stop',
            scheduled_departure: '2024-01-01T12:00:00Z',
            scheduled_arrival: null,
            realtime_departure: null,
            realtime_arrival: null,
            departure_delay_seconds: delay,
            arrival_delay_seconds: null,
            schedule_relationship: 'SCHEDULED',
            vehicle_id: null,
            alerts: [],
        })

        it('returns false for null delay', () => {
            expect(isDelayed(createDeparture(null))).toBe(false)
        })

        it('returns false for 0 delay', () => {
            expect(isDelayed(createDeparture(0))).toBe(false)
        })

        it('returns false for delays below default threshold (1 min)', () => {
            expect(isDelayed(createDeparture(29))).toBe(false) // 29 seconds rounds to 0
        })

        it('returns true for delays at or above default threshold (1 min)', () => {
            expect(isDelayed(createDeparture(60))).toBe(true) // 1 minute
            expect(isDelayed(createDeparture(120))).toBe(true) // 2 minutes
            expect(isDelayed(createDeparture(300))).toBe(true) // 5 minutes
        })

        it('respects custom threshold', () => {
            expect(isDelayed(createDeparture(120), 3)).toBe(false) // 2 min delay, 3 min threshold
            expect(isDelayed(createDeparture(180), 3)).toBe(true) // 3 min delay, 3 min threshold
            expect(isDelayed(createDeparture(300), 5)).toBe(true) // 5 min delay, 5 min threshold
            expect(isDelayed(createDeparture(269), 5)).toBe(false) // 4.48 min delay rounds to 4, 5 min threshold
        })

        it('returns false for early arrivals (negative delay)', () => {
            expect(isDelayed(createDeparture(-60))).toBe(false) // 1 minute early
            expect(isDelayed(createDeparture(-120))).toBe(false) // 2 minutes early
        })
    })

    describe('getEffectiveDepartureTime', () => {
        const createDeparture = (
            scheduled: string,
            realtime: string | null
        ): TransitDeparture => ({
            trip_id: 'trip1',
            route_id: 'route1',
            route_short_name: 'U1',
            route_long_name: 'U-Bahn 1',
            headsign: 'Destination',
            stop_id: 'stop1',
            stop_name: 'Stop',
            scheduled_departure: scheduled,
            scheduled_arrival: null,
            realtime_departure: realtime,
            realtime_arrival: null,
            departure_delay_seconds: null,
            arrival_delay_seconds: null,
            schedule_relationship: 'SCHEDULED',
            vehicle_id: null,
            alerts: [],
        })

        it('returns realtime when available', () => {
            const departure = createDeparture(
                '2024-01-01T12:00:00Z',
                '2024-01-01T12:05:00Z'
            )
            expect(getEffectiveDepartureTime(departure)).toBe('2024-01-01T12:05:00Z')
        })

        it('returns scheduled when realtime is null', () => {
            const departure = createDeparture('2024-01-01T12:00:00Z', null)
            expect(getEffectiveDepartureTime(departure)).toBe('2024-01-01T12:00:00Z')
        })
    })

    describe('getRouteTypeName', () => {
        it('returns correct name for TRAM', () => {
            expect(getRouteTypeName(GtfsRouteType.TRAM)).toBe('Tram')
        })

        it('returns correct name for METRO (U-Bahn)', () => {
            expect(getRouteTypeName(GtfsRouteType.METRO)).toBe('U-Bahn')
        })

        it('returns correct name for RAIL (S-Bahn)', () => {
            expect(getRouteTypeName(GtfsRouteType.RAIL)).toBe('S-Bahn/Bahn')
        })

        it('returns correct name for BUS', () => {
            expect(getRouteTypeName(GtfsRouteType.BUS)).toBe('Bus')
        })

        it('returns correct name for FERRY', () => {
            expect(getRouteTypeName(GtfsRouteType.FERRY)).toBe('Fähre')
        })

        it('returns correct name for CABLE_CAR', () => {
            expect(getRouteTypeName(GtfsRouteType.CABLE_CAR)).toBe('Seilbahn')
        })

        it('returns correct name for GONDOLA', () => {
            expect(getRouteTypeName(GtfsRouteType.GONDOLA)).toBe('Gondel')
        })

        it('returns correct name for FUNICULAR', () => {
            expect(getRouteTypeName(GtfsRouteType.FUNICULAR)).toBe('Standseilbahn')
        })

        it('returns "Unbekannt" for unknown route type', () => {
            expect(getRouteTypeName(999 as never)).toBe('Unbekannt')
        })
    })

    describe('getRouteTypeFromString', () => {
        it('returns METRO for U-Bahn routes', () => {
            expect(getRouteTypeFromString('U1')).toBe(GtfsRouteType.METRO)
            expect(getRouteTypeFromString('U6')).toBe(GtfsRouteType.METRO)
            expect(getRouteTypeFromString('u2')).toBe(GtfsRouteType.METRO) // lowercase
        })

        it('returns RAIL for S-Bahn routes', () => {
            expect(getRouteTypeFromString('S1')).toBe(GtfsRouteType.RAIL)
            expect(getRouteTypeFromString('S8')).toBe(GtfsRouteType.RAIL)
            expect(getRouteTypeFromString('s3')).toBe(GtfsRouteType.RAIL) // lowercase
        })

        it('returns TRAM for tram routes', () => {
            expect(getRouteTypeFromString('T12')).toBe(GtfsRouteType.TRAM)
            expect(getRouteTypeFromString('Tram 19')).toBe(GtfsRouteType.TRAM)
            expect(getRouteTypeFromString('t20')).toBe(GtfsRouteType.TRAM) // lowercase
        })

        it('returns BUS for bus routes', () => {
            expect(getRouteTypeFromString('B53')).toBe(GtfsRouteType.BUS)
            expect(getRouteTypeFromString('Bus 100')).toBe(GtfsRouteType.BUS)
        })

        it('defaults to BUS for unknown prefixes', () => {
            expect(getRouteTypeFromString('X50')).toBe(GtfsRouteType.BUS)
            expect(getRouteTypeFromString('100')).toBe(GtfsRouteType.BUS)
            expect(getRouteTypeFromString('Metrobus')).toBe(GtfsRouteType.BUS) // starts with M
        })

        it('handles empty string', () => {
            expect(getRouteTypeFromString('')).toBe(GtfsRouteType.BUS)
        })
    })
})
