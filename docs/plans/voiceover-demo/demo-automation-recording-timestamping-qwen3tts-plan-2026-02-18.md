# Demo Automation + Timestamping + Qwen3-TTS Plan (Cleaned)

**Date:** 2026-02-18

**Goal:** Produce a repeatable BahnVision demo video by (1) automating a deterministic UI journey, (2) capturing video + a machine-readable event timeline, and (3) adding synced narration audio (initially any TTS; optionally Qwen3 voice cloning later).

This is a feature plan and contract definition, not a step-by-step implementation guide.

## Scope

### In scope

- A Playwright-driven “demo run” that navigates a fixed, scripted path through the app.
- A timeline event log that records _when_ important UI and API milestones happen relative to the captured video.
- A narration pipeline that turns script lines into audio clips and aligns them to timeline anchors.
- A renderer that outputs a final MP4 plus a manifest describing exactly how it was produced.

### Non-goals (for this feature)

- A general-purpose screen-recording framework for arbitrary flows.
- Making production/live data deterministic (the narrated demo defaults to mocks/fixtures).
- Building a full UI for authoring scripts, timelines, or voice profiles.
- Shipping voice cloning without explicit consent, provenance, and audit metadata.

## Verified Current State (Repo Facts)

These statements have been verified by inspection of the current repository:

- Frontend routes and navigation exist and are easy to drive via Playwright: `/`, `/search`, `/station/:stationId`, `/monitoring` in `frontend/src/App.tsx`, and labeled nav links in `frontend/src/components/layout/AppLayout.tsx`.
- Playwright E2E tests already use stable, accessible selectors (`getByRole`) in `frontend/tests/e2e/flows/user-journeys.spec.ts`.
- Deterministic test data is already supported via Playwright route mocks in `frontend/tests/e2e/fixtures/mocks.ts`.
- Playwright base URL is configurable via `PLAYWRIGHT_BASE_URL` in `frontend/playwright.config.ts` (defaults to `:5173` when starting the dev server, otherwise `:3000`).
- A helper exists for launching Playwright’s Chromium with CDP enabled: `scripts/launch-playwright-chrome-cdp.sh` (useful for debugging; not required for the feature).
- Backend injects `X-Request-Id` on responses in `backend/app/main.py`.
- Backend heatmap endpoints emit `X-Cache-Status` and `Server-Timing` in `backend/app/api/v1/endpoints/heatmap.py`.
- Frontend fetch wrapper reads `X-Cache-Status` and `X-Request-Id` in `frontend/src/services/httpClient.ts`.

## Verified External Capability (Qwen3-TTS-Testing)

Qwen3-TTS is not implemented in this repo today. It exists as a separate repo that is already runnable on this machine:

- Location: `/home/burket/Git/QWEN3-TTS-Testing`
- Primary entrypoint: CLI hub `scripts/qwen_tts_hub.py` (subcommands include probe/download/list-speakers/custom/design/clone/benchmark).
- Execution wrapper: `scripts/run_in_env.sh` (sets cache/model/output environment variables for reproducible runs).
- Optional HTTP API: FastAPI wrapper under `web/backend/` exposing `POST /api/generate/custom`, `POST /api/generate/design`, and `POST /api/generate/clone` plus health/probe/download endpoints.

Behavioral notes that affect this feature:

- End-to-end synthesis to a WAV file works (custom mode with a local model snapshot and named speaker).
- GPU is optional (CPU works), but "auto" device selection uses CUDA when available.
- Voice cloning has extra preconditions: `sox` must be present and a reference audio file must be provided.
- Model downloads can occur via Hugging Face unless model snapshots are pre-provisioned under that repo's `models/` directory; deterministic narrated demos should not download during a run.

## Containerization Plan

For a Docker-first integration (no laptop host dependencies), track the TTS service work in:

- `docs/plans/voiceover-demo/qwen3-tts-thin-http-service-containerization-plan-2026-02-18.md`

## Core Simplifications (What This Plan Changes)

The original plan had the right building blocks but was over-specified in places. The main simplifications:

1. **Use relative timestamps as the source of truth.**

   - Store event times as `t_ms` since “capture start” (per run, or per scene).
   - Optionally store a wall-clock `utc` timestamp for debugging/audit, but never depend on it for sync.

2. **Start with one linear “demo run” video.**

   - MVP can be a single Playwright test that runs multiple “scenes” sequentially so the capture is one video (no concat logic needed).
   - Split into per-scene videos only if/when retries and partial re-renders become important.

3. **Treat “Qwen3-TTS voice cloning” as a plug-in, not a requirement.**
   - Define a minimal TTS adapter contract first (text in, audio out, duration out).
   - Integrate Qwen3 behind that interface by either calling the Qwen3 CLI hub through its env wrapper, or calling the Qwen3 FastAPI wrapper as a local service.
   - Treat voice cloning as a gated mode with explicit consent/provenance plus extra dependencies (reference audio + `sox`).

## Architecture (Stable Interfaces First)

### Inputs

- `demo script`: a structured representation of:
  - a sequence of actions to perform (navigation + interactions),
  - a narration script (lines),
  - and _anchors_ that connect narration lines to observed events (e.g., “say line 12 after heatmap data loads”).
- `voice profile` (optional at MVP): metadata describing what voice to use and how to reproduce it (provider/model ID, settings, and consent/audit fields).

### Capture (Playwright)

Deliverables:

- A deterministic demo run in Chromium that:
  - uses fixture/mocked data by default,
  - sets consistent viewport/locale/timezone,
  - captures a video artifact,
  - writes a structured event timeline log.

Event sources:

- UI milestones (e.g., “page loaded”, “map rendered”, “station selected”, “monitoring visible”).
- API milestones (e.g., response received for key endpoints, including response headers like `X-Request-Id`, `X-Cache-Status`, and `Server-Timing` when present).

### Narration (TTS Worker)

Deliverables:

- Generate one audio file per narration line.
- Persist:
  - input text,
  - output audio path/format,
  - computed duration (ms),
  - the exact model/provider/settings used.

Notes:

- For MVP, duration-only alignment is sufficient (line starts at an anchor; ends when audio ends).
- Word-level timestamps are optional and can be deferred unless subtitles must track words precisely.

### Qwen3-TTS Integration Options (Choose One)

Both options are viable given the current external repo state. Pick one as the default integration strategy for the demo pipeline.

Option A: CLI-based worker (recommended for early integration)

- Treat Qwen3 as an offline worker that writes WAV files to a known output directory.
- Pros: no long-running service, fewer moving parts, easy batch generation for many lines.
- Cons: process-per-line overhead unless you design a long-lived worker process.

Option B: HTTP-based worker

- Run the Qwen3 FastAPI wrapper and call it from the demo pipeline.
- Pros: clean separation, easier concurrency, centralized logging, and one place to enforce size limits/validation.
- Cons: extra service lifecycle management and port/config coordination.

Regardless of option, BahnVision should depend only on a stable adapter contract:

- Input: `text`, `mode` (custom/design/clone), voice selection (speaker or clone profile), and output format.
- Output: `audio_path` (or bytes), `duration_ms`, and synthesis metadata (model ID, device, settings).

### Compose + Render (FFmpeg)

Deliverables:

- A `timeline.json` that maps:
  - video segments (one segment for MVP),
  - narration clips,
  - and offsets/delays computed from anchors + clip durations.
- Render a final MP4 with narration mixed in (and optional loudness normalization and captions).

## Artifact Contract (Versioned and Testable)

Use a per-run directory (location/name is flexible; the important part is consistency).

Suggested structure:

- `<run_root>/manifest.json`
- `<run_root>/capture/demo.webm` (or `.mp4`)
- `<run_root>/events/events.ndjson`
- `<run_root>/tts/<line_id>.wav`
- `<run_root>/timeline/timeline.json`
- `<run_root>/final/demo.mp4`

### Event record shape (NDJSON)

Minimum viable event record:

```json
{
  "v": 1,
  "run_id": "2026-02-18T142315Z_local",
  "t_ms": 12500,
  "kind": "api_response",
  "page": "/",
  "data": {
    "method": "GET",
    "url": "/api/v1/heatmap/overview",
    "status": 200,
    "request_id": "abc-123",
    "cache_status": "hit",
    "server_timing": "cache;dur=9.20, total;dur=45.10"
  }
}
```

Notes:

- `t_ms` is the sync-critical field.
- `server_timing` can be stored raw (string) first; parsing into a structured object can be Phase 2.
- If/when per-scene capture is introduced, add `scene_id` and define whether `t_ms` is run-relative or scene-relative.

### Manifest essentials

The manifest is the “repro record” and should contain:

- Run ID, git commit SHA, and tool versions (Playwright, Chromium, FFmpeg, TTS provider/model).
- Determinism mode: `mocked` vs `live` (and which fixtures were used).
- Pointers to artifacts and their checksums (optional in MVP, recommended in hardening).

## Candidate Repo Placement (Non-Binding)

Keep this aligned with existing project structure and testing conventions:

- Playwright demo runner code: near existing E2E tests under `frontend/tests/e2e/` (e.g., a `demo/` subfolder).
- Any reusable capture/render orchestration scripts: `scripts/` (consistent with existing helper scripts).
- Schemas/contracts (if added): a new top-level `demo/` (or `demo/contracts/`) folder, so the artifacts aren’t “owned” by frontend test code.
- Execution runbook: a follow-up doc under `docs/` once behavior is stable (avoid writing a runbook before the contracts settle).

## Milestones (Expanded, With Acceptance Criteria)

### Phase 0: Decisions (before coding)

Decide and document:

- Is MVP one continuous capture, or per-scene capture?
- What are the minimum “anchor” events you’ll support (e.g., heatmap loaded, station page loaded, monitoring loaded)?
- What TTS baseline is acceptable for MVP (no voice cloning), and what consent/audit requirements gate voice cloning?

Acceptance:

- One-pager in this doc that records the decisions and the rationale.

### Phase 1: Deterministic Capture + Events (MVP foundation)

Deliver:

- A demo run that produces:
  - a video artifact,
  - an NDJSON event log with `t_ms`,
  - and enough events to anchor narration later.

Acceptance:

- Two runs with the same mock fixtures produce the same ordered sequence of event `kind`s, and similar `t_ms` values (allow small jitter; define an acceptable tolerance).
- Key API events contain `request_id` and `cache_status` when those headers are present.

### Phase 2: TTS Adapter + Narration Artifacts

Deliver:

- A TTS adapter interface and one concrete implementation (can be a placeholder provider initially).
- One audio clip per narration line with duration recorded.
- If using Qwen3: the adapter uses the verified external repo at `/home/burket/Git/QWEN3-TTS-Testing` via the chosen integration option (CLI or HTTP).

Acceptance:

- Re-running narration generation is deterministic given the same inputs and provider/settings.
- The manifest captures enough metadata to reproduce the output.
- For deterministic/demo mode: the run performs no model downloads; the selected model snapshot is pre-provisioned and referenced explicitly.

### Phase 3: Anchor Rules + Rendered MP4

Deliver:

- A `timeline.json` that schedules narration line starts from anchors (event-driven, not wall-clock).
- A rendered MP4 with narration mixed in at the intended times.

Acceptance:

- A human review can confirm “narration starts at the right moments” for the defined anchors.
- Automated check: every narration line references an existing anchor event, and scheduled start times are non-decreasing.

### Phase 4: Hardening (Only After MVP Works)

Deliver:

- Partial retry support (re-run only capture or only TTS).
- QC gates (missing anchors, missing audio, clipping detection, drift tolerance).
- Optional subtitles/captions generation.
- Voice cloning: add only with explicit consent, provenance, and an “approved voices” registry.

Acceptance:

- The pipeline fails fast with actionable errors when artifacts are missing or inconsistent.
- A short smoke demo can run in CI (optional; should not be flaky).

## Risks (Updated)

- **UI flakiness from async rendering (map, transitions):** rely on stable selectors and explicit “ready” milestones; default to mocks to reduce variability.
- **Timeline drift:** avoid wall-clock sync; use `t_ms` and anchor-based alignment.
- **Header availability differences (mocked vs live):** in mock mode, optionally inject representative `X-Cache-Status` and `Server-Timing` headers so downstream parsing is exercised.
- **Voice cloning safety/legal:** treat as a gated capability with consent and audit metadata; do not block MVP on it.
- **Hidden network dependency (model downloads):** Qwen3 may download from Hugging Face unless snapshots are local; mitigate by pre-downloading and pinning model directories, and failing fast if missing.
- **Extra clone preconditions:** clone mode requires `sox` and a valid reference audio file; mitigate by making clone mode opt-in with explicit inputs and validations.

## Open Questions (Answer Before/While Implementing)

- Do you want narration to wait for _UI-ready_ anchors (e.g., “heatmap visible”) or _API-ready_ anchors (e.g., “heatmap response received”), or both?
- Are you comfortable requiring FFmpeg as a local dependency for all developers, or should rendering be containerized?
- For Qwen3 integration, should the demo pipeline call the Qwen3 CLI hub (batch worker) or the Qwen3 FastAPI wrapper (local service)?
- Do you want to support clone mode in the first iteration, given it requires reference audio inputs and `sox`, or start with fixed speakers in custom/design mode?
- Does Qwen3-TTS provide stable output durations and (optionally) word timestamps, or will you need a separate forced-alignment step for captions?
