# GTFS Migration Strategy for BahnVision
**Date**: 2025-01-04  
**Purpose**: Comprehensive migration from MVG API to GTFS/GTFS-RT for national coverage and improved rate limiting
## Executive Summary
This document analyzes migrating BahnVision from Munich-specific MVG API to national GTFS/GTFS-RT infrastructure. The migration addresses rate limiting concerns while expanding coverage from Munich-only to Germany-wide transit data.
## Current State Analysis
### MVG API Integration
- **Scope**: Munich metropolitan area only
- **Data Sources**: Real-time API for all transit data
- **Rate Limits**: Unknown/undocumented (assumed lenient for moderate use)
- **Coverage**: ~18,214 stops in Munich area
- **Update Frequency**: Real-time (per request)
### Current Architecture
- **Primary Service**: `MVGClient` in `backend/app/services/mvg_client.py`
- **Data Models**: MVG-specific DTOs in `mvg_dto.py`
- **Caching**: Multi-layer with TTLs (30s-24h)
- **API Endpoints**: `/api/v1/mvg/` (stations, departures, routes)
## Migration Options Analysis
### Option 1: v6.db.transport.rest API
**Pros:**
- REST API, easier integration
- Country-wide coverage
- Official Deutsche Bahn backing
**Cons:**
- **Rate Limits**: 100 requests/minute (burst 200)
- **Lower limits than old HAFAS API**
- Requires new mapping layer
**Time Estimate**: 8-13 hours total
- API Client Development: 2-3 hours
- Data Model Updates: 1-2 hours  
- Service Layer Migration: 2-3 hours
- Testing & Validation: 1-2 hours
- Configuration & Deployment: 1 hour
- Rate Limit Analysis: 1-2 hours
### Option 2: GTFS/GTFS-RT Integration (Recommended)
**Pros:**
- **Massive Rate Limit Reduction**: 95% fewer API calls
- **10-Second Updates**: GTFS-RT stream updates every 10 seconds
- **National Coverage**: 500,000+ stops vs 18,214 Munich stops
- **Free & Open**: CC BY 4.0 license
- **Future-Proof**: EU-mandated national access point
**Cons:**
- Requires station ID mapping (MVG → GTFS format)
- More complex initial setup
- Need Protocol Buffer processing
**Time Estimate**: 6-10 hours total
- GTFS Foundation: 2-3 hours
- GTFS-RT Integration: 2-3 hours
- Smart Fallback Logic: 1-2 hours
- Testing & Migration: 1-2 hours
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
- **MVV-Specific**: Munich-only, availability issues
- **Regional Feeds**: Available for most German cities
## Station Mapping Requirements
### ID Format Incompatibility
**MVG Format**: `"de:09179:6210:2:2"` (proprietary hierarchical)
**GTFS Format**: Alphanumeric strings (e.g., `"de:09179"`, `"marienplatz_1"`, `"1001"`)
**Mapping Strategy:**
```python
# One-time mapping table creation
station_mappings = {
    "de:09179:6210:2:2": "de:09179",  # Marienplatz
    "de:09162:6": "marienplatz_s_bahn",  # Marienplatz S-Bahn
    # ... map all Munich stations
}
# Automated matching algorithm
def match_stations(mvg_stations, gtfs_stations):
    matches = {}
    for mvg in mvg_stations:
        # 1. Exact name match
        name_matches = [g for g in gtfs_stations 
                      if g.stop_name.lower() == mvg.name.lower()]
        
        # 2. Proximity match (within 50m)
        if not name_matches:
            proximity_matches = [g for g in gtfs_stations 
                            if distance(mvg.coords, g.coords) < 0.05]
            name_matches = proximity_matches
        
        # 3. Fuzzy name match
        if not name_matches:
            fuzzy_matches = [g for g in gtfs_stations 
                          if similarity(mvg.name, g.stop_name) > 0.8]
            name_matches = fuzzy_matches
        
        if name_matches:
            matches[mvg.id] = name_matches[0].stop_id
    return matches
```
## Implementation Architecture
### Hybrid Data Strategy
```python
class TransitDataService:
    def __init__(self):
        self.gtfs_schedule = GTFSScheduleService()
        self.gtfs_rt = GTFSRealtimeService()
        self.mvg_client = MVGClient()  # Fallback
        
    async def get_departures(self, station: str) -> List[Departure]:
        # 1. Get base schedule from GTFS
        scheduled = await self.gtfs_schedule.get_stop_departures(station)
        
        # 2. Apply real-time updates from GTFS-RT
        with_rt = await self.gtfs_rt.apply_delays(scheduled)
        
        # 3. Fallback to MVG if needed
        if not with_rt:
            return await self.mvg_client.get_departures(station)
            
        return with_rt
```
### Real-time Processing Pipeline
```python
class RealtimeDelayProcessor:
    def __init__(self):
        self.gtfs_rt_stream = "https://realtime.gtfs.de/realtime-free.pb"
        self.delay_buffer = {}  # Store recent delay data
        
    async def process_realtime_stream(self):
        """Process GTFS-RT stream every 10 seconds"""
        while True:
            # Fetch latest updates
            trip_updates = await self.fetch_gtfs_rt()
            
            # Calculate delays for heatmap
            delays = self.extract_delays(trip_updates)
            
            # Update heatmap data
            await self.update_heatmap(delays)
            
            await asyncio.sleep(10)  # Match stream update frequency
```
## Configuration Updates
### New Settings Required
```python
# Add to app/core/config.py
class Settings(BaseSettings):
    # GTFS Configuration
    gtfs_feed_url: str = Field(
        default="https://download.gtfs.de/germany/full/latest.zip",
        alias="GTFS_FEED_URL"
    )
    gtfs_rt_feed_url: str = Field(
        default="https://realtime.gtfs.de/realtime-free.pb",
        alias="GTFS_RT_FEED_URL"
    )
    gtfs_update_interval_hours: int = Field(
        default=24, alias="GTFS_UPDATE_INTERVAL_HOURS"
    )
    
    # Data source preferences
    prefer_gtfs_schedule: bool = Field(
        default=True, alias="PREFER_GTFS_SCHEDULE"
    )
    prefer_gtfs_rt: bool = Field(
        default=True, alias="PREFER_GTFS_RT"
    )
```
### Cache Strategy Updates
```python
# GTFS data caching (longer TTLs)
gtfs_schedule_cache_ttl_seconds: int = 43200  # 12 hours
gtfs_station_cache_ttl_seconds: int = 86400   # 24 hours
gtfs_rt_cache_ttl_seconds: int = 30          # 30 seconds (real-time)
```
## Migration Benefits
### Rate Limit Impact
- **Current**: 30+ requests/minute to MVG API
- **With GTFS**: 1 request/10 seconds to GTFS-RT + 1 daily GTFS download
- **Reduction**: ~95% fewer API calls
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
- Set up GTFS feed download service
- Implement GTFS parsing with `gtfs-kit`
- Create station mapping (MVG IDs → GTFS stop_ids)
- Build schedule query service
### Phase 2: GTFS-RT Integration (2-3 hours)
- Add GTFS-RT stream processing
- Implement delay/cancellation detection
- Create hybrid departure service (GTFS + RT overlay)
- Add "overload detection" logic for API fallback
### Phase 3: Smart Fallback (1-2 hours)
- Implement delay threshold detection
- Add v6.db.transport.rest client for high-delay scenarios
- Create intelligent switching logic
- Add monitoring for data quality
### Phase 4: Testing & Migration (1-2 hours)
- Compare data quality between sources
- Test rate limiting under load
- Validate delay detection accuracy
- Performance benchmarking
## Required Dependencies
### Python Libraries
```python
# Add to requirements.txt
gtfs-kit>=1.0.0              # GTFS parsing
protobuf>=4.0.0               # GTFS-RT processing
gtfs-realtime-bindings>=1.0.0  # Official GTFS-RT bindings
httpx>=0.24.0                  # HTTP client for GTFS downloads
```
### Database Schema Changes
```sql
-- Add station mapping table
CREATE TABLE station_mappings (
    mvg_station_id VARCHAR(64) PRIMARY KEY,
    gtfs_stop_id VARCHAR(64) NOT NULL,
    gtfs_feed_id VARCHAR(32),
    created_at TIMESTAMP DEFAULT NOW()
);
-- Add GTFS-specific fields to existing stations table
ALTER TABLE stations ADD COLUMN gtfs_stop_id VARCHAR(64);
ALTER TABLE stations ADD COLUMN gtfs_feed_source VARCHAR(32);
```
## Risk Assessment
### Technical Risks
- **Station Mapping Complexity**: MVG → GTFS ID conversion may have edge cases
- **GTFS-RT Latency**: 10-second updates may still miss ultra-rapid changes
- **Data Quality Differences**: GTFS schedule vs MVG real-time may have discrepancies
### Mitigation Strategies
- **Parallel Operation**: Run GTFS alongside MVG during transition
- **Gradual Rollout**: Switch endpoints one by one
- **Fallback Mechanisms**: Keep MVG as backup during transition
- **Quality Monitoring**: Continuous comparison of data sources
## Success Metrics
### Performance Targets
- **API Call Reduction**: >90% decrease in external API calls
- **Response Time**: <200ms for cached GTFS queries
- **Data Freshness**: <30 seconds for real-time information
- **Coverage Expansion**: From 18K to 500K+ stations
### Quality Targets
- **Data Accuracy**: >98% match rate for station mapping
- **Delay Detection**: <2 minute variance from ground truth
- **Service Availability**: >99.9% uptime with fallback mechanisms
## Next Steps
1. **Confirm GTFS.DE Feed Access**: Test download and parsing
2. **Validate GTFS-RT Stream**: Confirm 10-second update frequency
3. **Develop Station Mapping**: Create automated matching algorithm
4. **Implement Hybrid Service**: Build GTFS + RT + fallback architecture
5. **Performance Testing**: Validate rate limit reduction and response times
6. **Gradual Migration**: Switch endpoints with feature flags
7. **Monitor & Optimize**: Continuous improvement based on metrics
## Conclusion
GTFS/GTFS-RT integration provides the optimal path for BahnVision's expansion:
- **Solves rate limiting** through 95% API call reduction
- **Enables national coverage** beyond Munich limitations
- **Provides real-time freshness** with 10-second updates
- **Future-proofs the platform** with EU-mandated data standards
The migration effort (6-10 hours) is justified by long-term benefits in reliability, coverage, and operational efficiency.
---
**Document Version**: 1.0  
**Last Updated**: 2025-01-04  
**Next Review**: 2025-01-11