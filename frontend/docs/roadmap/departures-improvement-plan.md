# Departures Page Improvement Plan

> Status: Planned roadmap. Use this as aspirational guidance; align backend dependencies with `docs/tech-spec.md`.

## Phase 1: Fix Time & Date Selection UX
- Replace clunky `datetime-local` input with separate date picker and time selector components
- Add quick time preset buttons (e.g., "Now", "15 mins", "30 mins", "1 hour", "2 hours")
- Implement a proper calendar date picker with better mobile experience
- Add relative time display (e.g., "in 15 minutes", "tomorrow at 2:30 PM")

## Phase 2: Enhanced Refresh Status & UI
- Display last refresh timestamp with relative time (e.g., "Updated 2 seconds ago")
- Add countdown timer showing next auto-refresh
- Visual indicator for background refresh status (refreshing icon, success/error states)
- Expose cache status to users (fresh data, stale data, fetching, etc.)
- Add refresh progress indicator for slow operations

## Phase 3: Rate-Limited Manual Refreshes
- Implement manual refresh button with 10-second rate limiting
- Add visual cooldown indicator on refresh button
- Allow immediate refresh when switching between different time selections
- Implement optimistic UI updates for manual refreshes
- Add refresh queue to prevent multiple simultaneous requests

## Phase 4: Performance & State Management Improvements
- Simplify complex debouncing logic for transport filters
- Implement proper loading boundaries for different UI sections
- Add skeleton loading states for better perceived performance
- Improve error handling with retry mechanisms
- Add offline detection and cached data fallback

## Phase 5: Advanced Features
- Cache warming for popular stations/time combinations
- Smart refresh intervals based on data freshness needs
- Add "refresh all" for multiple station views
- Implement refresh notifications/permissions for background updates

**Files to be modified:**
- `frontend/src/pages/DeparturesPage.tsx` - Main UI improvements
- `frontend/src/hooks/useDepartures.ts` - Enhanced data fetching logic
- `frontend/src/components/` - New time/date picker components
- `backend/app/api/v1/endpoints/mvg/departures.py` - Cache optimization
- `backend/app/core/config.py` - TTL configuration updates

## Current Issues Identified

### Time/Date Selection Problems:
- The datetime-local input is clunky for mobile users
- No quick time presets (e.g., "15 mins", "1 hour", "tomorrow")
- Date changes require manual datetime input rather than calendar selection
- Timezone handling could be confusing for users

### Refresh Status Issues:
- Cache status headers aren't exposed to users
- No indication of when data was last fetched
- No visual feedback for background refresh failures
- Transport filter loading states could be clearer

### Performance & Caching:
- 30-second TTL might be too aggressive for historical/time-based queries
- No cache warming for popular stations
- Complex transport filter combinations can hit timeout issues

### State Management Complexity:
- Multiple state management systems (URL params, component state, debounced state)
- Potential race conditions between user interactions and auto-refresh
- Complex pagination logic mixing offset and time-based approaches

### Error Handling & Resilience:
- Limited retry mechanisms for failed requests
- No graceful degradation for network issues
- No offline support or cached data fallback
