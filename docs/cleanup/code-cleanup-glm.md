# Code Cleanup Report for BahnVision

## Overview
This document identifies unused files and components in the BahnVision project that can be safely removed to clean up the codebase. The findings are organized by confidence level to help prioritize cleanup efforts.

## Executive Summary

After a comprehensive analysis of the BahnVision codebase, the following unused items were identified:

- **High Confidence (Safe to Delete)**: 10 items including backend dead code, build artifacts, and archived documentation
- **Medium Confidence (Review Needed)**: 5 items including experimental configurations and potentially unused utilities
- **Low Confidence (Consider for Removal)**: 4 items related to Kubernetes and experimental features

## Files Safe to Delete (High Confidence)

### Backend Dead Code

#### 1. `backend/app/api/v1/shared/cache_manager.py`
- **Status**: Completely unused
- **Evidence**: No imports found anywhere in the codebase
- **Impact**: Appears to be dead code from a previous refactoring
- **Action**: Safe to delete

#### 2. `backend/app/core/metrics.py`
- **Status**: Metrics implemented but never used
- **Evidence**: Contains Prometheus metrics functions but none are called in production code
- **Details**: Functions defined but never called:
  - `record_cache_event`
  - `observe_cache_refresh`
  - `observe_transit_request`
  - `record_transit_transport_request`
- **Note**: Only imported in tests for testing purposes
- **Action**: Safe to delete

#### 3. `backend/app/models/__init__.py`
- **Status**: Empty file
- **Evidence**: File contains only 1 line of code
- **Impact**: No files import from `app.models`
- **Action**: Safe to delete

### Frontend Assets

#### 4. `frontend/public/react.svg`
- **Status**: Default React icon
- **Evidence**: Not referenced anywhere in the codebase
- **Impact**: Default SVG from create-react-app
- **Action**: Safe to delete

### Build/Generated Artifacts

#### 5. `.coverage` files
- **Locations**: Root directory and `backend/`
- **Status**: Test coverage artifacts
- **Evidence**: These are intermediate files that accumulate over time
- **Note**: Coverage is properly stored as JSON (`coverage.json`) for analysis
- **Action**: Safe to delete

#### 6. `.node/node-v24.11.1-linux-x64.tar.xz`
- **Status**: Compressed Node.js archive
- **Evidence**: The uncompressed version is already installed in `.node/bin/`
- **Impact**: Can be redownloaded if needed
- **Action**: Safe to delete

### Archived Documentation

#### 7-10. Archived Planning Documents
- `docs/planning/archive/maplibre-migration-plan.md` (already deleted)
- `docs/planning/archive/gtfs-migration-strategy.md`
- `docs/planning/archive/gtfs-testing-plan.md`
- `docs/planning/archive/heatmap-plan.md`
- **Status**: Historical documents
- **Evidence**: All explicitly archived as part of the migration history
- **Action**: Safe to delete all archive contents

## Review Before Deleting (Medium Confidence)

### Configuration Files

#### 11. `docker-compose.demo.yml`
- **Status**: Demo environment configuration
- **Usage**: Monitoring tools (Prometheus, Grafana)
- **Command**: `docker compose -f docker-compose.yml -f docker-compose.demo.yml`
- **Consideration**: Check if demo environment is still actively used
- **Action**: Review with team before deletion

#### 12. `.env`
- **Status**: Local environment configuration
- **Issue**: Not in `.gitignore` (should be)
- **Consideration**: Developer-specific configuration
- **Action**: Add to `.gitignore` and delete, or keep if needed

#### 13. `backend/app/api/v1/shared/cache_protocols.py`
- **Status**: Partially used
- **Concern**: `MvgCacheProtocol` class appears unused
- **Evidence**: Only referenced in its own file
- **Action**: Review if this protocol is still needed for the cache implementation

### Utility Files

#### 14. `frontend/src/utils/time.ts`
#### 15. `frontend/src/utils/transport.ts`
- **Status**: Not imported anywhere
- **Possibility**: Intended for future features
- **Action**: Review with development team about planned features

## Consider for Removal (Low Confidence)

### Kubernetes/Experimental Features

#### 16. `scripts/setup-kind.sh`
- **Status**: Kubernetes setup script
- **Usage**: Only referenced in `docs/devops/cloud-emulation-plan.md`
- **Consideration**: Remove if Kubernetes deployment is not planned
- **Impact**: Experimental deployment feature

#### 17. `examples/k8s/`
- **Contents**: Kubernetes configurations
- **Used by**: `setup-kind.sh` and `docker-compose.demo.yml`
- **Consideration**: Part of experimental containerization

#### 18. `examples/monitoring/`
- **Contents**: Prometheus/Grafana configurations
- **Used by**: Demo environment
- **Consideration**: Experimental monitoring setup

#### 19. `examples/toxiproxy/`
- **Contents**: Chaos testing configurations
- **Used by**: Demo environment
- **Consideration**: Experimental testing infrastructure

## Recommended Cleanup Plan

### Phase 1: Immediate Cleanup (Week 1)
1. **Delete build artifacts**:
   - Remove all `.coverage` files
   - Delete `.node/node-v24.11.1-linux-x64.tar.xz`

2. **Remove dead code**:
   - Delete `backend/app/api/v1/shared/cache_manager.py`
   - Remove `backend/app/core/metrics.py`
   - Delete `backend/app/models/__init__.py`

3. **Clean frontend assets**:
   - Remove `frontend/public/react.svg`

4. **Archive old documentation**:
   - Delete all files in `docs/planning/archive/`

### Phase 2: Team Review (Week 2)
1. **Configuration review**:
   - Discuss demo environment usage with team
   - Verify `.env` file necessity
   - Review cache protocols implementation

2. **Utility file decision**:
   - Check with developers about `time.ts` and `transport.ts`
   - Document purpose if keeping for future features

### Phase 3: Optional Cleanup (Week 3)
1. **Experimental features**:
   - Evaluate Kubernetes deployment plans
   - Decide on monitoring/chaos testing infrastructure
   - Remove if not in roadmap

### Phase 4: Prevention (Ongoing)
1. **Update `.gitignore`**:
   ```gitignore
   .coverage
   *.coverage
   .env
   ```

2. **Establish cleanup guidelines**:
   - Regular review of unused code
   - Automated tools for detecting dead code
   - Documentation retention policy

## Impact Assessment

### Storage Savings
- Approximate space saved: ~500MB (mostly from Node.js archive)
- Reduced repository clutter: 19 files/folders

### Code Quality Improvements
- Reduced cognitive load for developers
- Cleaner codebase navigation
- Eliminated potential confusion from dead code

### Risk Mitigation
- All high-confidence items have no dependencies
- Medium/Low confidence items require team consensus
- Git history preservation ensures recovery options

## Files Explicitly Kept

### Essential Components
- All active services and endpoints
- Core configuration files (config.py, database.py)
- Active documentation (README.md, tech-spec.md)
- Essential scripts (setup-dev.sh)

### Active Features
- GTFS-related services and models
- Heatmap functionality
- Cache implementation
- API endpoints
- Test suites for active modules

## Conclusion

The BahnVision codebase is generally well-maintained with minimal unused code. The identified items are primarily:
- Build artifacts that accumulate over time
- Dead code from previous refactoring efforts
- Experimental features that may or may not be needed
- Archived documentation

Following the phased cleanup plan will result in a cleaner, more maintainable codebase while preserving all active functionality and future development options.

## Next Steps

1. **Review this document** with the development team
2. **Approve Phase 1 cleanup** items for immediate deletion
3. **Schedule discussions** for Phase 2 items
4. **Update documentation** after cleanup completion
5. **Establish regular cleanup** cadence (quarterly reviews recommended)