# MVG Removal & Germany-Wide GTFS Refactor

## Objective

Remove all references to MVG (Münchner Verkehrsgesellschaft) and Munich-specific terminology from the BahnVision codebase. Refactor the application to be a **Germany-wide GTFS(-RT) transit data platform** rather than a Munich-specific MVG integration.

---

## Background

The codebase originally integrated with MVG's proprietary API for Munich transit data. The project has since migrated to standard GTFS (General Transit Feed Specification) and GTFS-RT (Realtime) data sources, which are:
- **Vendor-agnostic** - works with any transit agency publishing GTFS
- **Germany-wide** - can consume data from Deutsche Bahn, regional VVS, and other operators
- **Standards-based** - follows Google's GTFS specification

This refactor completes the transition by cleaning up legacy naming and documentation.

---

## Scope

### Files Requiring Changes

#### Documentation (High Priority)
- `README.md` - Project description, remove "Munich" focus
- `AGENTS.md` - Agent guidelines mentioning MVG
- `docs/tech-spec.md` - Technical specification with MVG references
- `docs/demo-guide.md` - Demo instructions
- `docs/local-setup.md` - Setup guide
- `docs/runtime-configuration.md` - Configuration docs
- `docs/testing/test-coverage-assessment.md`
- `docs/testing/coverage-implementation-plan.md`
- `docs/devops/cloud-emulation-plan.md`
- `docs/devops/pipeline-changes.md`
- `docs/devops/pipeline-plan.md`
- `docs/planning/feature-enhancement-plan.md`
- `docs/planning/archive/heatmap-plan.md`
- `docs/planning/archive/gtfs-testing-plan.md`
- `docs/planning/archive/gtfs-migration-strategy.md`
- `docs/planning/archive/maplibre-migration-plan.md`

#### Frontend
- `frontend/README.md` - Frontend docs
- `frontend/package.json` - Description field mentions "Munich"
- `frontend/tailwind.config.ts` - MVG color references?
- `frontend/src/services/api.ts` - API service
- `frontend/src/pages/MainPage.tsx` - Munich references
- `frontend/src/utils/time.ts` - Munich timezone comments?
- `frontend/tests/e2e/flows.spec.ts` - E2E test descriptions
- `frontend/src/tests/unit/useStationSearch.test.tsx` - Test data
- `frontend/docs/roadmap/*.md` - Roadmap documents
- `frontend/docs/operations/observability.md`
- `frontend/docs/product/ux-flows.md`

#### Backend
- `backend/README.md` - Backend docs
- `backend/requirements.runtime.txt` - Any MVG package references?
- `backend/app/core/telemetry.py` - Service name references
- `backend/app/models/transit.py` - Model definitions
- `backend/app/models/heatmap.py` - Heatmap models
- `backend/app/api/v1/shared/cache_protocols.py` - Cache key patterns
- `backend/tests/persistence/test_transit_data_repository.py` - Test fixtures
- `backend/tests/persistence/test_station_repository.py` - Station test data
- `backend/tests/fixtures/gtfs_data.py` - Munich-specific test fixtures
- `backend/scripts/load_test_fixtures.py` - Fixture loading
- `backend/alembic/README.md` - Migration docs

#### Infrastructure
- `examples/k8s/configmap.yaml` - K8s configuration
- `scripts/chaos-scenarios.sh` - Chaos testing scripts

---

## Refactoring Guidelines

### 1. Naming Changes

| Old Term | New Term | Notes |
|----------|----------|-------|
| MVG | GTFS / Transit | Generic transit terminology |
| Munich / München | Germany / DE | Broader geographic scope |
| Münchner Verkehrsgesellschaft | German transit operators | Generic description |
| MVG API | GTFS-RT feed | Standard data source |
| Munich transit | German public transit | Broader scope |
| MUNICH_CENTER | GERMANY_CENTER or make configurable | Map centering |

### 2. Code Changes

#### Constants & Defaults
```python
# Before
MUNICH_CENTER = [48.1351, 11.5820]
DEFAULT_TIMEZONE = "Europe/Berlin"  # Keep - still valid for Germany

# After
# Make center configurable or use Germany geographic center
GERMANY_CENTER = [51.1657, 10.4515]  # Geographic center of Germany
# Or make it configurable via environment variable
```

#### API Descriptions
```python
# Before
"""Fetches departure data from MVG API for Munich stations."""

# After
"""Fetches departure data from GTFS-RT feeds for German transit stations."""
```

#### Test Fixtures
Replace Munich-specific station names with generic German stations or use clearly fictional test data:
```python
# Before
stations = ["Marienplatz", "Hauptbahnhof", "Sendlinger Tor"]

# After
stations = ["Test Station A", "Test Station B", "Test Station C"]
# Or use a variety of German stations to show nationwide support
```

### 3. Documentation Updates

#### README.md Pattern
```markdown
# Before
BahnVision provides real-time transit data for Munich's public transportation network (MVG).

# After
BahnVision is a Germany-wide public transit data platform built on GTFS and GTFS-RT standards. It provides real-time departure information, service alerts, and cancellation analytics for German transit operators.
```

#### Feature Descriptions
```markdown
# Before
- Real-time departures for U-Bahn, S-Bahn, Tram, and Bus in Munich
- Integration with MVG's live data API

# After  
- Real-time departures for any German transit operator publishing GTFS-RT
- Standards-based GTFS/GTFS-RT integration (compatible with DB, regional operators)
- Support for U-Bahn, S-Bahn, Tram, Bus, and Regional services
```

### 4. Configuration Updates

Add/update environment variables for multi-region support:
```bash
# Make GTFS feed URL configurable (already exists)
GTFS_STATIC_FEED_URL=https://gtfs.de/de/free/latest.zip
GTFS_RT_FEED_URL=https://realtime.gtfs.de/realtime-free.pb

# Add optional map center override
MAP_DEFAULT_CENTER_LAT=51.1657
MAP_DEFAULT_CENTER_LNG=10.4515
MAP_DEFAULT_ZOOM=6
```

---

## Verification Checklist

After refactoring, verify:

- [ ] `grep -ri "mvg" .` returns no results (excluding git history)
- [ ] `grep -ri "munich" .` returns only appropriate geographic references (e.g., test data for Munich stations is acceptable if clearly labeled as example data)
- [ ] All tests pass: `pytest backend/tests` and `npm run test`
- [ ] Documentation accurately describes Germany-wide GTFS support
- [ ] API documentation reflects generic transit terminology
- [ ] Frontend UI text uses generic transit terms
- [ ] Map defaults to Germany-wide view (not zoomed into Munich)

---

## Out of Scope

- **Database migrations for existing data** - Existing station IDs and names are valid GTFS data regardless of operator
- **Changing the GTFS data source** - Already using gtfs.de Germany-wide feed
- **Removing Munich from GTFS test fixtures entirely** - Munich stations are valid test data, just don't hardcode Munich as the *only* region

---

## Priority Order

1. **High**: README.md, tech-spec.md, backend/README.md, frontend/README.md
2. **Medium**: Code files with MVG references, API descriptions
3. **Low**: Archived planning docs (can mark as historical), test fixtures (functional, just aesthetic)

---

## Notes

- The `backend/alembic/versions/80a6a8257627_rename_mvg_to_transit.py` migration already exists - this was a previous effort to rename MVG references in the database schema
- Some MVG references in archived docs (`docs/planning/archive/`) can be left as historical context with a note that they're outdated
- The `frontend/tailwind.config.ts` may have MVG brand colors - these should be renamed to generic transit colors or removed if not used

---

## Success Criteria

1. No functional MVG-specific code remains
2. Documentation describes BahnVision as a Germany-wide platform
3. New developers understand this is a GTFS-based system, not an MVG wrapper
4. Map and UI work for any German transit data, not just Munich
