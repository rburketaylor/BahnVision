# UI Design Upgrade: BVV-Style Transit Visualization

**Date:** 2026-01-21
**Status:** Design Approved
**Scope:** Heatmap/Map View UI, with design system foundation for broader application

## Overview

Upgrade BahnVision's UI to match German BVV/Dutch transit design aesthetics: high contrast, recognizable transit colors, bold typography, and functional polish. This design establishes a reusable foundation starting with the heatmap page.

## Design System Foundation

### Color Palette

**Brand Colors (Extended):**

- Primary: `#0065AE` (U-Bahn blue)
- Variants: `#4C9ACF` (light), `#004677` (dark)
- S-Bahn: `#00AB4E` (green) for healthy states
- Tram: `#D60F26` (red) for critical/alerts
- Bus: `#00558C` (dark blue)

**Status Colors:**

- Critical: Tram red gradient
- Warning: `#F59E0B` (amber)
- Healthy: S-Bahn green
- Neutral: Slate grays

**Surface Layers:**

- `bg-surface-1`: Lowest layer (map container)
- `bg-surface-2`: Mid layer (floating panels)
- `bg-surface-3`: Highest layer (popups, dropdowns)

### Typography System

**Scale (Tailwind classes):**
| Class | Size | Weight | Usage |
|------------|--------|--------|---------------------------|
| text-display | 28px | 700 | Page titles, hero headers |
| text-h1 | 24px | 700 | Section headers |
| text-h2 | 18px | 600 | Subsection headers |
| text-h3 | 16px | 600 | List item headers |
| text-body | 14px | 400 | Default content |
| text-small | 12px | 400 | Metadata, timestamps |
| text-tiny | 11px | 500 | Disclaimers, tips |

**Semantic Extensions:**

- `.text-brand`: Primary brand color for headings
- `.text-muted`: Softer color for secondary text
- Letter-spacing increase on all-caps text

**Number Display:**

- Tabular figures via `font-feature-settings: 'tnum'`

### Card & Surface Design

**Card Variants (left accent border):**

```css
.card-base           /* Base card style */
.card-accent-blue    /* Primary controls */
.card-accent-green   /* Healthy status */
.card-accent-red     /* Errors, critical */
.card-accent-orange  /* Warnings, delays */
```

**Card Structure:**

- 4px left border in accent color
- Subtle top shadow for depth
- Hover: lift (`-translate-y-0.5`) + shadow increase
- Padding: `p-4` (compact) or `p-5` (spacious)

### Micro-interactions

**Button/Interactive States:**

- Hover: `scale-105` + shadow increase (150ms)
- Active: `scale-98` for tactile feedback
- Focus: `ring-2 ring-brand ring-offset-2`

**Loading States:**

- Skeleton shimmer loaders
- Staggered fade-in for card lists
- Pulse on data refresh

**Panel Transitions:**

- Overlay toggle: slide from left (300ms cubic-bezier)
- Height transitions for collapse/expand (250ms)

**Map Marker Interactions:**

- Hover: scale 1.2x + glow
- Cluster click: ripple before zoom
- Popup: scaleIn from 95%

### Branded Map Markers

**Individual Stations:**

- Circular pin with white center, colored stroke
- Transport icon in center (U/S/Tram/Bus)
- Stroke color = severity level

**Clusters:**

- Larger circle with count badge
- Badge color = highest severity in cluster
- Ring glow indicates density

**Coverage/Healthy:**

- Small subtle dots (gray/blue)
- Indicates network coverage without implying issues

## Component Updates

### HeatmapOverlayPanel

- Blue accent strip on left edge
- Bold title (`text-h1`), subtle description (`text-small`)
- Button hover scale effects
- Stronger backdrop blur

### HeatmapControls

- Transport mode badges: circular icons
- Toggle switches with accent color tracks
- Pill-shaped time range selector
- All controls: hover lift + focus rings

### HeatmapStats

- Metric cards with color-coded accents
- Large tabular-figured numbers
- Pulse animation on refresh

### HeatmapLegend

- Gradient bar with labeled ticks
- Transport mode filter chips
- Interactive hover-to-highlight

### StationPopup

- Header with station name (`text-h2`)
- Colored values by severity
- Accent strip matching station status

### HeatmapSearchOverlay

- Search input with focus ring
- Staggered fade-in for results
- Selected state: blue accent strip

## Implementation Phases

1. **Foundation:** Update Tailwind config, add base CSS classes
2. **Base Components:** Create reusable Card, Badge components
3. **Overlay Panel:** Most visible component, establishes pattern
4. **Remaining Components:** Controls, Stats, Legend, Search
5. **Map Markers:** Custom SVG-based markers with React integration

## Accessibility

- All colors meet WCAG AA contrast requirements
- Transitions respect `prefers-reduced-motion`
- Focus indicators on all interactive elements
- Keyboard navigation maintained
