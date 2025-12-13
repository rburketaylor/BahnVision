# GTFS Migration Strategy for BahnVision

**Date**: 2025-12-04  
**Purpose**: Full migration to GTFS/GTFS-RT for national coverage  
**Status**: ✅ **COMPLETED** (2025-12-13)

## Executive Summary

This document outlines BahnVision's migration to national GTFS/GTFS-RT infrastructure. The migration provides Germany-wide transit data coverage with real-time updates and eliminates external API rate limiting concerns.

**Scope**: This is a complete migration—all existing MVG-specific code and endpoints will be removed and replaced with GTFS-based services.

> **Implementation Complete:** All phases implemented. See `gtfs-testing-plan.md` for test coverage details.

## Technology Stack

### Python-Native Approach

We use a fully Python-native solution that integrates with our existing FastAPI/SQLAlchemy stack:

| Component | Library | Purpose |
|-----------|---------|--------|
| GTFS Parsing | `gtfs-kit` | Load and analyze GTFS feeds in-memory with Pandas |
| Database ORM | `SQLAlchemy` | Persist GTFS data to PostgreSQL |
| GTFS-RT Processing | `gtfs-realtime-bindings` | Parse Protocol Buffer streams |
| HTTP Client | `httpx` | Async downloads for feeds and RT streams |
| Scheduling | `APScheduler` | Daily feed refresh jobs |

### Why Custom Over Third-Party Tools

We evaluated `gtfs-via-postgres` (Node.js) but chose a custom Python solution because:

1. **Stack Consistency**: Keeps everything in Python/SQLAlchemy - no Node.js runtime needed
2. **Schema Control**: We own the database schema and can extend it for custom fields
3. **License Simplicity**: gtfs-kit is MIT licensed (vs Prosperity license for gtfs-via-postgres)
4. **GTFS-RT Integration**: Neither tool handles real-time - we need to build it anyway
5. **Simpler Deployment**: No additional Docker containers or language runtimes

### gtfs-kit Capabilities

`gtfs-kit` (v12.x) provides:
- Feed loading from ZIP or directory
- In-memory analysis with Pandas DataFrames
- Correct handling of >24h times and DST transitions
- Stop/route/trip lookups and filtering
- Geographic operations via GeoPandas

**Note**: gtfs-kit is for analysis, not persistence. We extract DataFrames and load into PostgreSQL via SQLAlchemy.

## GTFS Architecture Overview
### GTFS/GTFS-RT Integration
**Benefits:**
- **Minimal External API Calls**: Only daily GTFS download + GTFS-RT stream
- **10-Second Updates**: GTFS-RT stream updates every 10 seconds
- **National Coverage**: 500,000+ stops across Germany
- **Free & Open**: CC BY 4.0 license
- **Future-Proof**: EU-mandated national access point

**Considerations:**
- Protocol Buffer processing required for GTFS-RT
- Initial GTFS feed download and parsing setup

**Time Estimate**: 8-13 hours total
- GTFS Foundation: 2-3 hours
- GTFS-RT Integration: 2-3 hours
- API & Frontend Updates: 2-3 hours
- Legacy Cleanup: 1-2 hours
- Testing & Validation: 1-2 hours
## Recommended Data Sources
### Primary: GTFS.DE (National Germany)
**Why Best Choice:**
- **Official EU Mandated Access Point**
- **Complete Coverage**: 20,000+ lines, 500,000+ stops, 2M+ journeys
- **Daily Updates**: Fresh schedule data
- **Free GTFS-RT**: Real-time stream included
- **Multiple Feed Options**:
  - `de_full`: Complete Germany (recommended)
  - `de_fv`: Long distance rail
  - `de_rv`: Regional rail
  - `de_nv`: Local/urban transit
**Update Frequencies:**
- **Static GTFS**: Daily updates
- **GTFS-RT Stream**: Every 10 seconds
- **Format**: Protocol Buffer (`.pb`)
### Secondary Sources
- **DELFI**: German government initiative, primarily standards body
- **Regional Feeds**: Available for most German cities (VBB Berlin, VRS Cologne, etc.)
## Implementation Architecture

### Feed Import Pipeline

```python
import gtfs_kit as gk
from sqlalchemy.ext.asyncio import AsyncSession

class GTFSFeedImporter:
    """Import GTFS feed into PostgreSQL using gtfs-kit + SQLAlchemy."""
    
    def __init__(self, session: AsyncSession, storage_path: str):
        self.session = session
        self.storage_path = Path(storage_path)
    
    async def import_feed(self, feed_url: str) -> str:
        """Download, parse, and persist GTFS feed."""
        # 1. Download feed
        feed_path = await self._download_feed(feed_url)
        
        # 2. Load with gtfs-kit (in-memory Pandas DataFrames)
        feed = gk.read_feed(feed_path, dist_units="km")
        
        # 3. Generate feed_id for tracking
        feed_id = f"gtfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 4. Persist to PostgreSQL via SQLAlchemy
        await self._persist_stops(feed.stops, feed_id)
        await self._persist_routes(feed.routes, feed_id)
        await self._persist_trips(feed.trips, feed_id)
        await self._persist_stop_times(feed.stop_times, feed_id)
        await self._persist_calendar(feed.calendar, feed.calendar_dates, feed_id)
        
        # 5. Record feed metadata
        await self._record_feed_info(feed, feed_id, feed_url)
        
        return feed_id
    
    async def _persist_stops(self, stops_df: pd.DataFrame, feed_id: str):
        """Bulk insert stops from DataFrame."""
        records = [
            GTFSStop(
                stop_id=row.stop_id,
                stop_name=row.stop_name,
                stop_lat=row.stop_lat,
                stop_lon=row.stop_lon,
                location_type=getattr(row, 'location_type', 0),
                parent_station=getattr(row, 'parent_station', None),
                feed_id=feed_id,
            )
            for row in stops_df.itertuples()
        ]
        # Use bulk insert for performance
        await self.session.execute(
            insert(GTFSStop).values([r.__dict__ for r in records])
            .on_conflict_do_update(index_elements=['stop_id'], set_={...})
        )
```

### Schedule Query Service

```python
class GTFSScheduleService:
    """Query scheduled departures from PostgreSQL."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_stop_departures(
        self,
        stop_id: str,
        from_time: datetime,
        limit: int = 20,
    ) -> list[ScheduledDeparture]:
        """Get scheduled departures for a stop."""
        # Determine which service_ids are active today
        today = from_time.date()
        weekday = today.strftime('%A').lower()  # 'monday', 'tuesday', etc.
        
        query = text("""
            SELECT 
                st.departure_time,
                t.trip_headsign,
                r.route_short_name,
                r.route_long_name,
                r.route_type,
                r.route_color,
                s.stop_name
            FROM gtfs_stop_times st
            JOIN gtfs_trips t ON st.trip_id = t.trip_id
            JOIN gtfs_routes r ON t.route_id = r.route_id
            JOIN gtfs_stops s ON st.stop_id = s.stop_id
            JOIN gtfs_calendar c ON t.service_id = c.service_id
            LEFT JOIN gtfs_calendar_dates cd 
                ON t.service_id = cd.service_id AND cd.date = :today
            WHERE st.stop_id = :stop_id
              AND c.start_date <= :today AND c.end_date >= :today
              AND (
                  -- Regular service day
                  (c.{weekday} = true AND (cd.exception_type IS NULL OR cd.exception_type != 2))
                  -- Or added via calendar_dates
                  OR cd.exception_type = 1
              )
              AND st.departure_time >= :from_interval
            ORDER BY st.departure_time
            LIMIT :limit
        """.format(weekday=weekday))
        
        result = await self.session.execute(query, {
            'stop_id': stop_id,
            'today': today,
            'from_interval': time_to_interval(from_time),
            'limit': limit,
        })
        
        return [ScheduledDeparture.from_row(row) for row in result]
```

### Transit Data Service (with RT overlay)

```python
class TransitDataService:
    """Combines scheduled data with real-time updates."""
    
    def __init__(self, schedule: GTFSScheduleService, realtime: GTFSRealtimeService):
        self.schedule = schedule
        self.realtime = realtime
        
    async def get_departures(self, stop_id: str, from_time: datetime) -> list[Departure]:
        # 1. Get base schedule from PostgreSQL
        scheduled = await self.schedule.get_stop_departures(stop_id, from_time)
        
        if not scheduled:
            raise StopNotFoundError(f"Stop {stop_id} not found in GTFS feed")
        
        # 2. Apply real-time updates from GTFS-RT (graceful degradation)
        try:
            return await self.realtime.apply_delays(scheduled)
        except GTFSRealtimeUnavailable:
            logger.warning("GTFS-RT unavailable, returning scheduled times")
            return [Departure.from_scheduled(s) for s in scheduled]
```
### Real-time Processing Pipeline
```python
class RealtimeDelayProcessor:
    def __init__(self, settings: Settings):
        self.gtfs_rt_url = settings.gtfs_rt_feed_url
        self.timeout = settings.gtfs_rt_timeout_seconds
        self.delay_buffer: dict[str, TripDelay] = {}
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60
        )
        
    async def process_realtime_stream(self):
        """Process GTFS-RT stream every 10 seconds"""
        while True:
            try:
                if self.circuit_breaker.is_open:
                    logger.warning("Circuit breaker open, skipping GTFS-RT fetch")
                    await asyncio.sleep(10)
                    continue
                    
                # Fetch with timeout
                async with asyncio.timeout(self.timeout):
                    trip_updates = await self.fetch_gtfs_rt()
                
                # Reset circuit breaker on success
                self.circuit_breaker.record_success()
                
                # Calculate and store delays
                delays = self.extract_delays(trip_updates)
                await self.update_heatmap(delays)
                
            except (asyncio.TimeoutError, httpx.RequestError) as e:
                self.circuit_breaker.record_failure()
                logger.error(f"GTFS-RT fetch failed: {e}")
                
            await asyncio.sleep(10)  # Match stream update frequency
```
## Configuration Updates

### New Settings Required
```python
# Add to app/core/config.py
class Settings(BaseSettings):
    # GTFS Static Feed Configuration
    gtfs_feed_url: str = Field(
        default="https://download.gtfs.de/germany/full/latest.zip",
        alias="GTFS_FEED_URL"
    )
    gtfs_update_interval_hours: int = Field(
        default=24, alias="GTFS_UPDATE_INTERVAL_HOURS"
    )
    gtfs_max_feed_age_hours: int = Field(
        default=48, alias="GTFS_MAX_FEED_AGE_HOURS"  # Force re-download if older
    )
    gtfs_download_timeout_seconds: int = Field(
        default=300, alias="GTFS_DOWNLOAD_TIMEOUT"  # 5 min for large feed
    )
    gtfs_storage_path: str = Field(
        default="/data/gtfs", alias="GTFS_STORAGE_PATH"
    )
    
    # GTFS-RT Configuration
    gtfs_rt_feed_url: str = Field(
        default="https://realtime.gtfs.de/realtime-free.pb",
        alias="GTFS_RT_FEED_URL"
    )
    gtfs_rt_timeout_seconds: int = Field(
        default=10, alias="GTFS_RT_TIMEOUT"
    )
    gtfs_rt_circuit_breaker_threshold: int = Field(
        default=3, alias="GTFS_RT_CIRCUIT_BREAKER_THRESHOLD"
    )
    gtfs_rt_circuit_breaker_recovery_seconds: int = Field(
        default=60, alias="GTFS_RT_CIRCUIT_BREAKER_RECOVERY"
    )
```

### Cache Strategy
```python
# GTFS data caching TTLs
gtfs_schedule_cache_ttl_seconds: int = 43200  # 12 hours
gtfs_stop_cache_ttl_seconds: int = 86400      # 24 hours
gtfs_rt_cache_ttl_seconds: int = 30           # 30 seconds (real-time)
```

### Environment Variables
```bash
# .env.example
GTFS_FEED_URL=https://download.gtfs.de/germany/full/latest.zip
GTFS_RT_FEED_URL=https://realtime.gtfs.de/realtime-free.pb
GTFS_STORAGE_PATH=/data/gtfs
GTFS_UPDATE_INTERVAL_HOURS=24
GTFS_RT_TIMEOUT=10
```
## GTFS Benefits

### Minimal External API Dependencies
- **GTFS Static**: 1 daily download of schedule data
- **GTFS-RT**: Streaming updates every 10 seconds
- **No Rate Limiting Concerns**: Data is cached locally
### Performance Improvements
- **Faster Response Times**: Local GTFS data
- **Better Reliability**: Less external dependency
- **Offline Capability**: Cached GTFS data
### Data Quality
- **More Comprehensive Coverage**: National vs Munich-focused
- **Better Schedule Accuracy**: Official timetable data
- **Richer Metadata**: Route shapes, stop facilities
## Implementation Phases

### Phase 1: GTFS Foundation (2-3 hours)
**Files to create:**
- `backend/app/models/gtfs.py` - SQLAlchemy models
- `backend/app/services/gtfs_feed.py` - Feed download and import
- `backend/app/services/gtfs_schedule.py` - Schedule queries
- `backend/alembic/versions/xxx_add_gtfs_tables.py` - Migration

**Tasks:**
- Set up GTFS feed download with httpx + retry logic
- Implement feed parsing with gtfs-kit
- Create Alembic migration for GTFS tables
- Build `GTFSFeedImporter` to persist DataFrames to PostgreSQL
- Add APScheduler job for daily feed refresh
- Create `GTFSScheduleService` for departure queries

### Phase 2: GTFS-RT Integration (2-3 hours)
**Files to create:**
- `backend/app/services/gtfs_realtime.py` - RT stream processing
- `backend/app/services/transit_data.py` - Combined service

**Tasks:**
- Add GTFS-RT stream fetching with Protocol Buffers
- Implement `GTFSRealtimeService` with circuit breaker
- Create `TransitDataService` (schedule + RT overlay)
- Add service alerts processing
- Implement delay/cancellation detection
- Store RT data in Valkey for fast lookups

### Phase 3: API & Frontend Updates (2-3 hours)
**Files to create:**
- `backend/app/api/v1/endpoints/transit/` - New endpoint module
- `frontend/src/services/endpoints/transitApi.ts` - API client
- `frontend/src/types/gtfs.ts` - TypeScript types

**Tasks:**
- Create new `/api/v1/transit/` endpoints
- Update frontend services to consume new API
- Update TypeScript types for GTFS data models
- Test end-to-end integration

### Phase 4: Legacy Cleanup (1-2 hours)
**Files to remove:**
- `backend/app/services/mvg_client.py`
- `backend/app/models/mvg_dto.py`
- `backend/app/api/v1/endpoints/mvg/`
- `frontend/src/services/endpoints/mvgApi.ts`

**Tasks:**
- Remove all MVG-related code
- Update imports and dependencies
- Run full test suite to confirm no regressions
- Update documentation

### Phase 5: Testing & Validation (1-2 hours)
**Tasks:**
- Validate data quality and completeness
- Test real-time update accuracy and graceful degradation
- Performance benchmarking (target: <200ms for departures)
- Load testing with concurrent requests
- Verify Prometheus metrics are collecting

**Revised Total Estimate**: 8-13 hours
## Required Dependencies

### Python Libraries
```
# Add to requirements.txt
gtfs-kit==12.0.0              # GTFS parsing with Pandas (MIT license)
protobuf==4.25.1              # GTFS-RT Protocol Buffer processing
gtfs-realtime-bindings==1.0.0 # Official Google GTFS-RT bindings
httpx==0.27.0                 # Async HTTP client for downloads
apscheduler==3.10.4           # Job scheduling for daily feed updates
geopandas==0.14.0             # Required by gtfs-kit for geo operations
```

**Notes**:
- Pin exact versions for reproducible builds
- `gtfs-kit` requires Python 3.10+ and uses ~500MB RAM for full Germany feed
- `geopandas` brings GDAL/GEOS dependencies - use the `geopandas` Docker base image or install via conda

### System Requirements
```
# For geopandas spatial operations
apt-get install -y libgdal-dev libgeos-dev

# Or use conda (recommended for geo dependencies)
conda install -c conda-forge geopandas
```
### Database Schema Changes
```sql
-- GTFS stops table
CREATE TABLE gtfs_stops (
    stop_id VARCHAR(64) PRIMARY KEY,
    stop_name VARCHAR(255) NOT NULL,
    stop_lat DECIMAL(9,6),
    stop_lon DECIMAL(9,6),
    location_type SMALLINT DEFAULT 0,  -- 0=stop, 1=station, 2=entrance
    parent_station VARCHAR(64),
    platform_code VARCHAR(16),
    feed_id VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_gtfs_stops_name ON gtfs_stops(stop_name);
CREATE INDEX idx_gtfs_stops_location ON gtfs_stops(stop_lat, stop_lon);

-- GTFS routes table
CREATE TABLE gtfs_routes (
    route_id VARCHAR(64) PRIMARY KEY,
    agency_id VARCHAR(64),
    route_short_name VARCHAR(64),
    route_long_name VARCHAR(255),
    route_type SMALLINT NOT NULL,  -- 0=tram, 1=metro, 2=rail, 3=bus, etc.
    route_color VARCHAR(6),
    feed_id VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW()
);

-- GTFS trips table (links routes to stop_times)
CREATE TABLE gtfs_trips (
    trip_id VARCHAR(64) PRIMARY KEY,
    route_id VARCHAR(64) NOT NULL REFERENCES gtfs_routes(route_id),
    service_id VARCHAR(64) NOT NULL,
    trip_headsign VARCHAR(255),
    direction_id SMALLINT,
    feed_id VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_gtfs_trips_route ON gtfs_trips(route_id);
CREATE INDEX idx_gtfs_trips_service ON gtfs_trips(service_id);

-- GTFS stop_times table (actual departure/arrival times)
CREATE TABLE gtfs_stop_times (
    id SERIAL PRIMARY KEY,
    trip_id VARCHAR(64) NOT NULL REFERENCES gtfs_trips(trip_id),
    stop_id VARCHAR(64) NOT NULL REFERENCES gtfs_stops(stop_id),
    arrival_time INTERVAL,    -- Can exceed 24h for overnight trips
    departure_time INTERVAL,
    stop_sequence SMALLINT NOT NULL,
    pickup_type SMALLINT DEFAULT 0,
    drop_off_type SMALLINT DEFAULT 0,
    feed_id VARCHAR(32)
);
CREATE INDEX idx_gtfs_stop_times_stop ON gtfs_stop_times(stop_id);
CREATE INDEX idx_gtfs_stop_times_trip ON gtfs_stop_times(trip_id);

-- GTFS calendar table (service schedules)
CREATE TABLE gtfs_calendar (
    service_id VARCHAR(64) PRIMARY KEY,
    monday BOOLEAN NOT NULL,
    tuesday BOOLEAN NOT NULL,
    wednesday BOOLEAN NOT NULL,
    thursday BOOLEAN NOT NULL,
    friday BOOLEAN NOT NULL,
    saturday BOOLEAN NOT NULL,
    sunday BOOLEAN NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    feed_id VARCHAR(32)
);

-- GTFS calendar_dates table (service exceptions)
CREATE TABLE gtfs_calendar_dates (
    service_id VARCHAR(64) NOT NULL,
    date DATE NOT NULL,
    exception_type SMALLINT NOT NULL,  -- 1=added, 2=removed
    feed_id VARCHAR(32),
    PRIMARY KEY (service_id, date)
);

-- Feed metadata tracking
CREATE TABLE gtfs_feed_info (
    feed_id VARCHAR(32) PRIMARY KEY,
    feed_url VARCHAR(512),
    downloaded_at TIMESTAMP NOT NULL,
    feed_start_date DATE,
    feed_end_date DATE,
    stop_count INTEGER,
    route_count INTEGER,
    trip_count INTEGER
);

-- Performance-critical composite indexes for departure queries
CREATE INDEX idx_gtfs_stop_times_departure_lookup 
    ON gtfs_stop_times(stop_id, departure_time);
CREATE INDEX idx_gtfs_calendar_active 
    ON gtfs_calendar(start_date, end_date);
CREATE INDEX idx_gtfs_calendar_dates_lookup 
    ON gtfs_calendar_dates(date, service_id);

-- Full-text search on stop names (optional, for autocomplete)
CREATE INDEX idx_gtfs_stops_name_trgm 
    ON gtfs_stops USING gin(stop_name gin_trgm_ops);
```

### SQLAlchemy Models

```python
# backend/app/models/gtfs.py
from sqlalchemy import Column, String, Integer, SmallInteger, Boolean, Date, Interval
from sqlalchemy.orm import relationship
from app.persistence.models import Base

class GTFSStop(Base):
    __tablename__ = "gtfs_stops"
    
    stop_id = Column(String(64), primary_key=True)
    stop_name = Column(String(255), nullable=False, index=True)
    stop_lat = Column(Numeric(9, 6))
    stop_lon = Column(Numeric(9, 6))
    location_type = Column(SmallInteger, default=0)
    parent_station = Column(String(64))
    platform_code = Column(String(16))
    feed_id = Column(String(32))

class GTFSRoute(Base):
    __tablename__ = "gtfs_routes"
    
    route_id = Column(String(64), primary_key=True)
    agency_id = Column(String(64))
    route_short_name = Column(String(64))
    route_long_name = Column(String(255))
    route_type = Column(SmallInteger, nullable=False)
    route_color = Column(String(6))
    feed_id = Column(String(32))
    
    trips = relationship("GTFSTrip", back_populates="route")

class GTFSTrip(Base):
    __tablename__ = "gtfs_trips"
    
    trip_id = Column(String(64), primary_key=True)
    route_id = Column(String(64), ForeignKey("gtfs_routes.route_id"), nullable=False)
    service_id = Column(String(64), nullable=False, index=True)
    trip_headsign = Column(String(255))
    direction_id = Column(SmallInteger)
    feed_id = Column(String(32))
    
    route = relationship("GTFSRoute", back_populates="trips")
    stop_times = relationship("GTFSStopTime", back_populates="trip")

class GTFSStopTime(Base):
    __tablename__ = "gtfs_stop_times"
    
    id = Column(Integer, primary_key=True)
    trip_id = Column(String(64), ForeignKey("gtfs_trips.trip_id"), nullable=False)
    stop_id = Column(String(64), ForeignKey("gtfs_stops.stop_id"), nullable=False)
    arrival_time = Column(Interval)
    departure_time = Column(Interval)
    stop_sequence = Column(SmallInteger, nullable=False)
    pickup_type = Column(SmallInteger, default=0)
    drop_off_type = Column(SmallInteger, default=0)
    feed_id = Column(String(32))
    
    trip = relationship("GTFSTrip", back_populates="stop_times")
```
## Risk Assessment

### Technical Risks
- **GTFS Feed Size**: Full Germany feed is large (~500MB+), requires storage planning
- **GTFS-RT Latency**: 10-second updates may miss ultra-rapid changes
- **Feed Availability**: GTFS.DE downtime could impact schedule updates
- **Data Completeness**: Some regional operators may have incomplete GTFS data

### Mitigation Strategies
- **Aggressive Caching**: Cache GTFS data locally with 12-24 hour TTL
- **Circuit Breakers**: Graceful degradation if GTFS-RT stream fails
- **Multiple Feed Sources**: Configure backup GTFS feeds (regional/national)
- **Quality Monitoring**: Track data completeness and freshness metrics
## Success Metrics

### Performance Targets
- **Response Time**: <200ms for cached GTFS queries
- **Data Freshness**: <30 seconds for real-time information
- **Coverage**: 500,000+ stops across Germany

### Quality Targets
- **Data Completeness**: >99% of scheduled trips available
- **Delay Detection**: <2 minute variance from ground truth
- **Service Availability**: >99.9% uptime with cached data fallback
## Next Steps

1. **Validate Data Sources** (Pre-work)
   - Test GTFS.DE feed download (~500MB)
   - Confirm GTFS-RT stream parsing with Protocol Buffers
   - Measure feed download time and storage requirements

2. **Implement GTFS Services**
   - Create `GTFSFeedService` for feed management
   - Create `GTFSScheduleService` for schedule queries
   - Create `GTFSRealtimeService` for RT updates

3. **Create API Endpoints**
   - `GET /api/v1/transit/stops` - Search/list stops
   - `GET /api/v1/transit/stops/{stop_id}/departures` - Departures with RT
   - `GET /api/v1/transit/routes/{route_id}` - Route details
   - `GET /api/v1/transit/delays` - Delay heatmap data

4. **Update Frontend**
   - Update `services/api.ts` for new endpoints
   - Update components to use GTFS data models

5. **Remove Legacy Code**
   - Delete MVG client, DTOs, and endpoints
   - Run full test suite to confirm no regressions

6. **Deploy & Monitor**
   - Add Prometheus metrics for GTFS feed health
   - Set up alerts for feed staleness and RT failures
## Conclusion

GTFS/GTFS-RT provides the foundation for BahnVision's transit data:

- **National coverage** with 500,000+ stops across Germany
- **Real-time freshness** with 10-second GTFS-RT updates
- **No rate limiting concerns** with locally cached data
- **Future-proof** with EU-mandated data standards

The implementation effort (8-13 hours) enables reliable, comprehensive transit data coverage while fully removing legacy MVG dependencies.

---
**Document Version**: 3.0 (Final)  
**Last Updated**: 2025-12-13  
**Status**: Implementation Complete