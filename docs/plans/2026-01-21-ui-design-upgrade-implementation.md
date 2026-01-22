# UI Design Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade BahnVision's heatmap UI to BVV/Dutch transit design aesthetic with bold typography, color-accented cards, micro-interactions, and branded map markers.

**Architecture:** Incremental updates to existing heatmap components. Start with Tailwind config + CSS foundation, then create reusable base components (Card, Badge), then update heatmap components one by one.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, MapLibre GL, Vitest for testing.

**Branch:** `feat/ui-design-upgrade`
**Worktree:** `.worktrees/ui-design-upgrade`

---

## Phase 1: Design System Foundation

### Task 1.1: Extend Tailwind Config with Typography Scale

**Files:**

- Modify: `frontend/tailwind.config.ts`

**Step 1: Add new typography scale to theme.extend**

Add these entries under `theme.extend` in the Tailwind config:

```typescript
fontSize: {
  display: ['28px', '36px'],   // 700 weight - page titles, hero headers
  h1: ['24px', '32px'],        // 700 weight - section headers
  h2: ['18px', '26px'],        // 600 weight - subsection headers
  h3: ['16px', '24px'],        // 600 weight - list item headers
  body: ['14px', '22px'],      // 400 weight - default content
  small: ['12px', '18px'],     // 400 weight - metadata, timestamps
  tiny: ['11px', '16px'],      // 500 weight - disclaimers, tips
},
```

**Step 2: Add surface colors for layering**

```typescript
colors: {
  // ... existing colors ...

  // Surface layers for visual hierarchy
  surface: {
    1: '#121212',  // Lowest layer (map container)
    2: '#1E1E1E',  // Mid layer (floating panels)
    3: '#252525',  // Highest layer (popups, dropdowns)
  },

  // Light mode surfaces
  'light-surface': {
    1: '#ffffff',
    2: '#f9fafb',
    3: '#f3f4f6',
  },
},
```

**Step 3: Add status colors**

```typescript
colors: {
  // ... existing colors ...

  // Status colors for metrics
  status: {
    critical: '#D60F26',  // Tram red
    warning: '#F59E0B',   // Amber
    healthy: '#00AB4E',   // S-Bahn green
    neutral: '#6b7280',   // Slate gray
  },
},
```

**Step 4: Run typecheck to verify config**

Run: `cd frontend && npm run type-check`
Expected: No errors

**Step 5: Commit**

```bash
git add frontend/tailwind.config.ts
git commit -m "feat: add typography scale and surface colors to Tailwind config"
```

---

### Task 1.2: Add Card Base Classes to CSS

**Files:**

- Modify: `frontend/src/index.css`

**Step 1: Add card base classes**

Add these CSS classes after the existing semantic tokens section (after line ~65):

```css
/*
 * BVV-Style Card System
 * Color-accented left borders for visual hierarchy
 */

/* Base card with subtle depth */
.card-base {
  background-color: var(--bg-card, #1e1e1e);
  border-radius: 8px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.05);
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

html:not(.dark) .card-base {
  background-color: #ffffff;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.03);
}

.card-base:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

html:not(.dark) .card-base:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* Compact card padding */
.card-compact {
  padding: 1rem; /* p-4 */
}

/* Spacious card padding */
.card-spacious {
  padding: 1.25rem; /* p-5 */
}

/* Color-accented left borders */
.card-accent-blue {
  border-left: 4px solid #0065ae;
}

.card-accent-green {
  border-left: 4px solid #00ab4e;
}

.card-accent-red {
  border-left: 4px solid #d60f26;
}

.card-accent-orange {
  border-left: 4px solid #f59e0b;
}

.card-accent-gray {
  border-left: 4px solid #6b7280;
}

/* Surface layer backgrounds */
.bg-surface-1 {
  background-color: #121212 !important;
}

html:not(.dark) .bg-surface-1 {
  background-color: #ffffff !important;
}

.bg-surface-2 {
  background-color: #1e1e1e !important;
}

html:not(.dark) .bg-surface-2 {
  background-color: #f9fafb !important;
}

.bg-surface-3 {
  background-color: #252525 !important;
}

html:not(.dark) .bg-surface-3 {
  background-color: #f3f4f6 !important;
}
```

**Step 2: Add typography utility classes**

```css
/*
 * BVV-Style Typography
 */

.text-display {
  font-size: 28px;
  line-height: 36px;
  font-weight: 700;
}

.text-h1 {
  font-size: 24px;
  line-height: 32px;
  font-weight: 700;
}

.text-h2 {
  font-size: 18px;
  line-height: 26px;
  font-weight: 600;
}

.text-h3 {
  font-size: 16px;
  line-height: 24px;
  font-weight: 600;
}

.text-body {
  font-size: 14px;
  line-height: 22px;
  font-weight: 400;
}

.text-small {
  font-size: 12px;
  line-height: 18px;
  font-weight: 400;
}

.text-tiny {
  font-size: 11px;
  line-height: 16px;
  font-weight: 500;
}

/* Brand-colored text */
.text-brand {
  color: #0065ae !important;
}

html:not(.dark) .text-brand {
  color: #0065ae !important;
}

/* Tabular figures for data */
.font-tabular {
  font-feature-settings: "tnum";
  font-variant-numeric: tabular-nums;
}
```

**Step 3: Add micro-interaction utilities**

```css
/*
 * Micro-interaction Utilities
 */

/* Hover scale for buttons */
.hover-scale {
  transition: transform 0.15s ease;
}

.hover-scale:hover {
  transform: scale(1.05);
}

.hover-scale:active {
  transform: scale(0.98);
}

/* Focus ring with brand color */
.focus-ring:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px #0065ae,
    0 0 0 4px rgba(0, 101, 174, 0.2);
}

html:not(.dark) .focus-ring:focus-visible {
  box-shadow:
    0 0 0 2px #0065ae,
    0 0 0 4px rgba(0, 101, 174, 0.15);
}

/* Ripple animation for map interactions */
@keyframes ripple {
  0% {
    transform: scale(1);
    opacity: 0.5;
  }
  100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

.ripple-effect {
  animation: ripple 0.6s ease-out;
}
```

**Step 4: Run tests to verify no CSS issues**

Run: `cd frontend && npm run test -- --run`
Expected: All 198 tests pass

**Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: add BVV-style card system, typography, and micro-interaction utilities"
```

---

## Phase 2: Base UI Components

### Task 2.1: Create Reusable Card Component

**Files:**

- Create: `frontend/src/components/ui/Card.tsx`
- Create: `frontend/src/components/ui/Card.test.tsx`

**Step 1: Write the test first**

```tsx
// frontend/src/components/ui/Card.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card } from "./Card";

describe("Card", () => {
  it("renders with base styling", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("applies accent variant class", () => {
    const { container } = render(<Card accent="blue">Blue accent</Card>);
    expect(container.firstChild).toHaveClass("card-accent-blue");
  });

  it("applies compact padding by default", () => {
    const { container } = render(<Card>Content</Card>);
    expect(container.firstChild).toHaveClass("card-compact");
  });

  it("applies spacious padding when specified", () => {
    const { container } = render(<Card padding="spacious">Content</Card>);
    expect(container.firstChild).toHaveClass("card-spacious");
  });

  it("applies custom className", () => {
    const { container } = render(<Card className="custom-class">Content</Card>);
    expect(container.firstChild).toHaveClass("custom-class");
  });

  it("renders with additional props", () => {
    render(<Card data-testid="test-card">Content</Card>);
    expect(screen.getByTestId("test-card")).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run Card.test.tsx`
Expected: FAIL with "Cannot find module './Card'"

**Step 3: Implement the Card component**

```tsx
// frontend/src/components/ui/Card.tsx
import React from "react";

export type CardAccent = "blue" | "green" | "red" | "orange" | "gray";
export type CardPadding = "compact" | "spacious";

export interface CardProps extends React.ComponentProps<"div"> {
  /** Accent color for left border */
  accent?: CardAccent;
  /** Padding variant */
  padding?: CardPadding;
  /** Children content */
  children: React.ReactNode;
}

export function Card({
  accent,
  padding = "compact",
  className,
  children,
  ...props
}: CardProps) {
  const classes = [
    "card-base",
    padding === "compact" ? "card-compact" : "card-spacious",
    accent ? `card-accent-${accent}` : "",
    className || "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} {...props}>
      {children}
    </div>
  );
}
```

**Step 4: Export from ui index**

Create `frontend/src/components/ui/index.ts`:

```tsx
export { Card } from "./Card";
export type { CardProps, CardAccent, CardPadding } from "./Card";
```

**Step 5: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run Card.test.tsx`
Expected: PASS (5 tests)

**Step 6: Run all tests to ensure no regression**

Run: `cd frontend && npm run test -- --run`
Expected: All 203 tests pass (198 + 5 new)

**Step 7: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat: add reusable Card component with accent variants"
```

---

### Task 2.2: Create Badge Component for Transport Modes

**Files:**

- Create: `frontend/src/components/ui/Badge.tsx`
- Create: `frontend/src/components/ui/Badge.test.tsx`

**Step 1: Write the test first**

```tsx
// frontend/src/components/ui/Badge.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders with text content", () => {
    render(<Badge>U</Badge>);
    expect(screen.getByText("U")).toBeInTheDocument();
  });

  it("applies transport mode colors", () => {
    const { container } = render(<Badge mode="ubahn">U</Badge>);
    expect(container.firstChild).toHaveStyle({ backgroundColor: "#0065AE" });
  });

  it("applies sbahn mode color", () => {
    const { container } = render(<Badge mode="sbahn">S</Badge>);
    expect(container.firstChild).toHaveStyle({ backgroundColor: "#00AB4E" });
  });

  it("applies tram mode color", () => {
    const { container } = render(<Badge mode="tram">T</Badge>);
    expect(container.firstChild).toHaveStyle({ backgroundColor: "#D60F26" });
  });

  it("applies bus mode color", () => {
    const { container } = render(<Badge mode="bus">B</Badge>);
    expect(container.firstChild).toHaveStyle({ backgroundColor: "#00558C" });
  });

  it("applies small size", () => {
    const { container } = render(<Badge size="small">U</Badge>);
    expect(container.firstChild).toHaveClass("badge-small");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run Badge.test.tsx`
Expected: FAIL with "Cannot find module './Badge'"

**Step 3: Implement the Badge component**

```tsx
// frontend/src/components/ui/Badge.tsx
import React from "react";

export type TransportMode = "ubahn" | "sbahn" | "tram" | "bus";
export type BadgeSize = "small" | "medium" | "large";

const MODE_COLORS: Record<TransportMode, string> = {
  ubahn: "#0065AE", // Blue
  sbahn: "#00AB4E", // Green
  tram: "#D60F26", // Red
  bus: "#00558C", // Dark blue
};

const SIZES: Record<BadgeSize, string> = {
  small: "w-6 h-6 text-xs",
  medium: "w-8 h-8 text-sm",
  large: "w-10 h-10 text-base",
};

export interface BadgeProps {
  /** Transport mode for color */
  mode?: TransportMode;
  /** Size variant */
  size?: BadgeSize;
  /** Badge content (usually a letter) */
  children: React.ReactNode;
  /** Additional className */
  className?: string;
}

export function Badge({
  mode = "ubahn",
  size = "medium",
  className,
  children,
  ...props
}: BadgeProps) {
  const baseClasses =
    "rounded-full flex items-center justify-center font-semibold text-white";
  const sizeClasses = SIZES[size];
  const customClasses = className || "";

  return (
    <span
      className={`${baseClasses} ${sizeClasses} ${customClasses}`}
      style={{ backgroundColor: MODE_COLORS[mode] }}
      {...props}
    >
      {children}
    </span>
  );
}
```

**Step 4: Export from ui index**

Add to `frontend/src/components/ui/index.ts`:

```tsx
export { Card } from "./Card";
export type { CardProps, CardAccent, CardPadding } from "./Card";

export { Badge } from "./Badge";
export type { BadgeProps, TransportMode, BadgeSize } from "./Badge";
```

**Step 5: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run Badge.test.tsx`
Expected: PASS (6 tests)

**Step 6: Run all tests to ensure no regression**

Run: `cd frontend && npm run test -- --run`
Expected: All 209 tests pass

**Step 7: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat: add Badge component for transport modes"
```

---

## Phase 3: Heatmap Component Updates

### Task 3.1: Update HeatmapOverlayPanel with New Styling

**Files:**

- Modify: `frontend/src/components/heatmap/HeatmapOverlayPanel.tsx`
- Modify: `frontend/src/tests/unit/HeatmapOverlayPanel.test.tsx` (if exists, create if not)

**Step 1: Read current component to understand structure**

Run: `cat frontend/src/components/heatmap/HeatmapOverlayPanel.tsx`

**Step 2: Apply new styling**

Key changes to make:

1. Wrap panel content in `Card` component with `accent="blue"`
2. Change title to use `text-h2` class
3. Add `text-small` for description text
4. Add hover-scale effects to buttons

**Step 3: Update test to match new structure**

Ensure tests still pass with the new Card-wrapped structure.

**Step 4: Run tests**

Run: `cd frontend && npm run test -- --run HeatmapOverlayPanel.test.tsx`
Expected: PASS

**Step 5: Run all tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 6: Commit**

```bash
git add frontend/src/components/heatmap/HeatmapOverlayPanel.tsx
git add frontend/src/tests/unit/HeatmapOverlayPanel.test.tsx
git commit -m "feat: apply BVV styling to HeatmapOverlayPanel"
```

---

### Task 3.2: Update HeatmapStats with Color-Accented Cards

**Files:**

- Modify: `frontend/src/components/heatmap/HeatmapStats.tsx`
- Modify: `frontend/src/tests/unit/HeatmapStats.test.tsx`

**Step 1: Add severity-based accent color logic**

Create a helper function that returns accent color based on metric value:

- `cancellationRate > 0.1`: red
- `cancellationRate > 0.05`: orange
- otherwise: green

**Step 2: Update each metric stat to use Card component**

Apply appropriate accent color based on severity.

**Step 3: Add `font-tabular` class to metric values**

For consistent number alignment.

**Step 4: Update tests**

Ensure tests pass with new Card structure.

**Step 5: Run tests**

Run: `cd frontend && npm run test -- --run HeatmapStats.test.tsx`
Expected: PASS

**Step 6: Run all tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 7: Commit**

```bash
git add frontend/src/components/heatmap/HeatmapStats.tsx
git add frontend/src/tests/unit/HeatmapStats.test.tsx
git commit -m "feat: apply BVV styling to HeatmapStats with severity-based accents"
```

---

### Task 3.3: Update HeatmapControls with Transport Mode Badges

**Files:**

- Modify: `frontend/src/components/heatmap/HeatmapControls.tsx`
- Modify: `frontend/src/tests/unit/HeatmapControls.test.tsx`

**Step 1: Replace mode labels with Badge components**

Use the Badge component for U-Bahn, S-Bahn, Tram, Bus indicators.

**Step 2: Style toggle switches**

Add accent color tracks for active toggle states.

**Step 3: Add hover-lift effects to all controls**

Apply `hover-scale` class to interactive elements.

**Step 4: Update tests**

Ensure Badge components render correctly in tests.

**Step 5: Run tests**

Run: `cd frontend && npm run test -- --run HeatmapControls.test.tsx`
Expected: PASS

**Step 6: Run all tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 7: Commit**

```bash
git add frontend/src/components/heatmap/HeatmapControls.tsx
git add frontend/src/tests/unit/HeatmapControls.test.tsx
git commit -m "feat: apply BVV styling to HeatmapControls with transport badges"
```

---

### Task 3.4: Update HeatmapLegend Styling

**Files:**

- Modify: `frontend/src/components/heatmap/HeatmapLegend.tsx`
- Test file may not exist - create if needed

**Step 1: Apply Card styling with gray accent**

**Step 2: Add gradient bar for intensity scale**

Use CSS gradient for the legend bar.

**Step 3: Update tests or create new test file**

**Step 4: Run tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 5: Commit**

```bash
git add frontend/src/components/heatmap/HeatmapLegend.tsx
git commit -m "feat: apply BVV styling to HeatmapLegend"
```

---

### Task 3.5: Update HeatmapSearchOverlay Styling

**Files:**

- Modify: `frontend/src/components/heatmap/HeatmapSearchOverlay.tsx`
- Modify: `frontend/src/tests/unit/HeatmapSearchOverlay.test.tsx`

**Step 1: Style search input with focus-ring class**

**Step 2: Apply Card styling to result items**

Add blue accent on selected items.

**Step 3: Add staggered fade-in for results**

Use `stagger-animation` class on results list.

**Step 4: Run tests**

Run: `cd frontend && npm run test -- --run HeatmapSearchOverlay.test.tsx`
Expected: PASS

**Step 5: Run all tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 6: Commit**

```bash
git add frontend/src/components/heatmap/HeatmapSearchOverlay.tsx
git add frontend/src/tests/unit/HeatmapSearchOverlay.test.tsx
git commit -m "feat: apply BVV styling to HeatmapSearchOverlay"
```

---

### Task 3.6: Update StationPopup Styling

**Files:**

- Modify: `frontend/src/components/heatmap/StationPopup.tsx`
- Test file may not exist - create if needed

**Step 1: Apply typography hierarchy**

Use `text-h2` for station name, `text-small` for labels.

**Step 2: Add font-tabular to metric values**

**Step 3: Style the Details link button**

Add `hover-scale` and `focus-ring` classes.

**Step 4: Create test file if it doesn't exist**

**Step 5: Run tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 6: Commit**

```bash
git add frontend/src/components/heatmap/StationPopup.tsx
git commit -m "feat: apply BVV styling to StationPopup"
```

---

### Task 3.7: Update Map Popup CSS (injected HTML)

**Files:**

- Modify: `frontend/src/index.css` (the `.bv-map-popup` styles)

**Step 1: Update popup typography**

Apply the new typography scale to popup classes.

**Step 2: Add accent strip to popup**

Add left border matching severity color.

**Step 3: Update popup link button**

Add hover effects.

**Step 4: Update `.bv-map-popup` CSS**

Update the existing styles in `index.css`:

```css
.bv-map-popup {
  min-width: 200px;
  max-width: 280px;
  box-sizing: border-box;
  overflow: hidden;
  /* Add left accent strip - blue by default */
  border-left: 4px solid #0065ae;
  padding-left: 12px; /* Reduce left padding since border adds visual space */
}

.bv-map-popup__title {
  margin: 0 0 8px;
  padding-right: 44px;
  font-weight: 700; /* Increased from 600 */
  font-size: 18px; /* Increased from 14px */
  line-height: 26px;
  word-break: break-word;
  hyphens: auto;
}

.bv-map-popup__rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px; /* Increased from 13px */
}

.bv-map-popup__row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  min-height: 20px;
  align-items: center;
}

.bv-map-popup__label {
  color: #6b7280;
  flex-shrink: 1;
  min-width: 0;
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
  font-size: 12px;
}

html.dark .bv-map-popup__label {
  color: rgba(224, 224, 224, 0.72);
}

.bv-map-popup__label--active {
  font-weight: 600;
}

.bv-map-popup__value {
  font-weight: 600;
  text-align: right;
  flex-shrink: 0;
  font-feature-settings: "tnum"; /* Tabular figures */
}

.bv-map-popup__link {
  display: block;
  margin-top: 12px;
  padding: 8px 12px;
  text-align: center;
  font-size: 14px; /* Increased from 13px */
  font-weight: 600;
  color: #ffffff;
  background-color: #0065ae;
  border-radius: 8px;
  text-decoration: none;
  transition:
    background-color 0.15s ease,
    transform 0.15s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bv-map-popup__link:hover {
  background-color: #0054a0;
  transform: scale(1.05); /* Scale effect */
}

.bv-map-popup__link:active {
  transform: scale(0.98);
}
```

**Step 5: Run tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 6: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: update map popup styling with BVV typography and accents"
```

---

## Phase 4: Branded Map Markers (Optional Enhancement)

### Task 4.1: Create Custom Marker Component

**Files:**

- Create: `frontend/src/components/map/StationMarker.tsx`
- Create: `frontend/src/components/map/StationMarker.test.tsx`

**Note:** This is an advanced task that may require significant MapLibre integration. Consider deferring to future iteration.

---

## Final Steps

### Task 5.1: Run Full Test Suite

**Step 1: Run all frontend tests**

Run: `cd frontend && npm run test -- --run`
Expected: All tests pass

**Step 2: Run typecheck**

Run: `cd frontend && npm run type-check`
Expected: No type errors

**Step 3: Run linter**

Run: `cd frontend && npm run lint`
Expected: No lint errors

---

### Task 5.2: Visual Review

**Step 1: Start dev server**

Run: `cd frontend && npm run dev`

**Step 2: Manual testing checklist**

- [ ] Navigate to `/heatmap` page
- [ ] Verify HeatmapOverlayPanel has blue accent strip
- [ ] Verify stats cards have color-coded accents
- [ ] Verify transport badges show correct colors
- [ ] Verify legend displays properly
- [ ] Verify search overlay has focus rings
- [ ] Verify station popup has proper typography
- [ ] Verify all hover effects work
- [ ] Verify dark/light mode both work
- [ ] Verify responsive behavior

**Step 3: Take screenshots for PR**

Capture before/after if possible.

---

### Task 5.3: Prepare for Merge

**Step 1: Rebase onto develop**

```bash
git checkout develop
git pull
git checkout feat/ui-design-upgrade
git rebase develop
```

**Step 2: Resolve any conflicts**

If conflicts occur, resolve them and:

```bash
git add .
git rebase --continue
```

**Step 3: Push to remote**

```bash
git push -u origin feat/ui-design-upgrade
```

**Step 4: Create PR**

Use the following PR template:

```
## Summary
- Implements BVV/Dutch transit design aesthetic for heatmap page
- Added typography scale, color-accented card system, and micro-interactions
- Created reusable Card and Badge components

## Changes
- Extended Tailwind config with typography scale and surface colors
- Added CSS utility classes for cards, typography, and interactions
- Created `Card` and `Badge` base components
- Updated all heatmap components with new styling

## Testing
- All 200+ existing tests passing
- Manual visual review completed
- Dark/light mode verified

## Screenshots
<!-- Attach screenshots -->
```

---

## Completion Criteria

- [ ] All 7 phases completed
- [ ] All tests pass (no regression)
- [ ] Typecheck passes
- [ ] Linter passes
- [ ] Manual visual review completed
- [ ] PR created and ready for review
