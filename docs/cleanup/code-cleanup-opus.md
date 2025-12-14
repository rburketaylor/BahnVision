# Code Cleanup Findings

**Date:** 2025-12-14  
**Status:** Assessment Complete

This document identifies unused code, deprecated items, and cleanup opportunities in the BahnVision codebase.

---

## 1. Deprecated NPM Dependency

| Package | Location | Issue |
|---------|----------|-------|
| `@types/dompurify` | `frontend/package.json` | Stub types package - DOMPurify v3+ includes its own TypeScript definitions |

**Fix:** `npm uninstall @types/dompurify`

---

## 2. Unused Route Planning Code

Route planning is disabled (Phase 5+ planned feature). The following are non-functional placeholders:

| File | Item | Notes |
|------|------|-------|
| `frontend/src/hooks/useRoutePlanner.ts` | `useRoutePlannerLegacy` export | Never imported anywhere |
| `frontend/src/types/api.ts` | `RouteStop`, `RouteLeg`, `RoutePlan`, `RoutePlanResponse`, `RoutePlanParams` | Only used by disabled hook |
| `frontend/src/pages/PlannerPage.tsx` | Entire page | "Coming Soon" placeholder |
| `frontend/src/tests/unit/useRoutePlanner.test.tsx` | Test file | Tests disabled functionality |

**Decision needed:** Keep as scaffolding for future work, or remove entirely?

---

## 3. Legacy MVG References

Per `docs/planning/mvg-removal-refactor.md`, these files contain outdated MVG branding:

### High Priority (User-facing docs)
- `README.md` - References "MVG API", "Munich transit"
- `frontend/README.md` - API endpoints listed as `/api/v1/mvg/*`
- `frontend/package.json` - Description: "Munich transit live data dashboard"

### Medium Priority (Code/Config)
- `AGENTS.md` - Mentions "MVG client", "Fake Valkey/MVG doubles"
- `frontend/tailwind.config.ts` - Comments: "MVG brand colors", "MVG blue"
- `examples/k8s/configmap.yaml` - Env vars: `MVG_DEPARTURES_CACHE_TTL_*`, etc.
- `scripts/chaos-scenarios.sh` - Reference to "MVG API calls"
- `frontend/tests/e2e/flows.spec.ts` - Mock routes for `/api/v1/mvg/*`

### Low Priority (Internal docs)
- `frontend/docs/product/ux-flows.md` - `/api/v1/mvg/*` endpoints
- `frontend/docs/operations/observability.md` - `/api/v1/mvg/` reference
- `docs/devops/cloud-emulation-plan.md` - "cache/MVG metrics" mentions

---

## 4. Archived Planning Documents

These in `docs/planning/archive/` describe completed work:

| File | Status |
|------|--------|
| `gtfs-migration-strategy.md` | ✅ Migration complete |
| `gtfs-testing-plan.md` | ✅ Tests implemented |
| `heatmap-plan.md` | ✅ Feature shipped |
| `maplibre-migration-plan.md` | ✅ Migration complete |

**Recommendation:** Add "ARCHIVED - Historical Reference" header or delete.

---

## 5. Miscellaneous

| Item | Location | Issue |
|------|----------|-------|
| `.coverage` | Project root | 53KB coverage data file - should be in `.gitignore` |

---

## Recommended Cleanup Order

1. **Quick wins** (5 min)
   - Remove `@types/dompurify` dependency
   - Verify `.coverage` is gitignored

2. **MVG naming cleanup** (30-60 min)
   - Follow `docs/planning/mvg-removal-refactor.md` checklist
   - Update README, package.json descriptions
   - Rename config env vars

3. **Route planner decision** (depends on product roadmap)
   - If Phase 5 is >3 months away, consider removing scaffolding
   - If near-term, keep as placeholders

4. **Archive docs housekeeping** (10 min)
   - Add headers or delete archived plans
