# Qwen3-TTS Thin HTTP Service Containerization Plan

**Date:** 2026-02-18

**Goal:** Add a containerized, laptop-friendly Qwen3-TTS HTTP service that the BahnVision demo automation can call, without requiring host installs of PyTorch, `sox`, or Hugging Face caches.

This is a feature plan. It defines boundaries, contracts, and the Compose topology, but intentionally avoids a step-by-step implementation guide.

## Current State (Verified)

- BahnVision repo has no Qwen/TTS implementation today (only planning docs). See `docs/plans/voiceover-demo/demo-automation-recording-timestamping-qwen3tts-plan-2026-02-18.md`.
- The working Qwen harness lives in a separate local repo: `/home/burket/Git/QWEN3-TTS-Testing`.
  - It provides a CLI (`scripts/qwen_tts_hub.py`) and a FastAPI wrapper (`web/backend/app.py`), and uses an env wrapper (`scripts/run_in_env.sh`) to keep caches/outputs in-repo.
- BahnVision already uses Docker Compose for dev (`docker-compose.yml`), and is a good place to add an optional “voiceover demo” profile/service.

## Recommended Integration Approach

### Principle: keep Qwen in a separate service

Do not embed Qwen3-TTS into the BahnVision backend image. Instead:

- Add a dedicated `qwen-tts` service to Compose.
- The demo pipeline (capture/render orchestration) talks to it over HTTP.

Rationale:

- Keeps the BahnVision backend image small and fast to build.
- Avoids forcing PyTorch/`sox` and model/cache management onto all backend developers.
- Makes laptop usage consistent (everything behind `docker compose`).

### Preferred API style: thin FastAPI wrapper over the supported library API

Implement the service as a thin FastAPI app that calls the upstream-supported library API (`qwen-tts` / `qwen_tts`) directly, rather than shelling out to a CLI.

Notes:

- The `/home/burket/Git/QWEN3-TTS-Testing` repo is a useful reference implementation, but it is not itself a “supported upstream contract”.
- A thin service that uses the library API can still mirror the endpoint shapes you already validated in the harness repo.

## Placement in This Repo

Put container/service code under `voiceover-demo/tts-http/` at repo root, and keep planning docs under `docs/plans/voiceover-demo/`.

Planned files (names are suggestions, not requirements):

- `voiceover-demo/tts-http/app/main.py` (FastAPI app)
- `voiceover-demo/tts-http/requirements.txt` (pinned)
- `voiceover-demo/tts-http/Dockerfile` (CPU-first base)
- `voiceover-demo/tts-http/README.md` (minimal service contract and operational constraints, not a full runbook)

## Compose Topology

Add a new optional Compose service to `docker-compose.yml`.

Service name:

- `qwen-tts`

Profiles:

- `voiceover` (CPU-first, runs everywhere)
- Optional later: `voiceover-gpu` (NVIDIA GPU passthrough if desired)

Volumes (named, not bind mounts):

- `qwen_tts_models` mounted at `/models`
- `qwen_tts_cache` mounted at `/cache`
- `qwen_tts_outputs` mounted at `/outputs`

Environment defaults (match the proven harness pattern):

- `HF_HOME=/cache/huggingface`
- `HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub`
- `TORCH_HOME=/cache/torch`
- `XDG_CACHE_HOME=/cache/xdg`
- `QWEN_TTS_MODEL_DIR=/models`
- `QWEN_TTS_OUTPUT_DIR=/outputs`

Ports:

- Expose the HTTP API on an internal network name (`http://qwen-tts:8000`) for other services.
- Optionally publish to host (for debugging), but the demo pipeline should not require host port exposure.

## Determinism and Model Provisioning

Narrated demo runs must be deterministic and should not depend on network access.

Rules:

- The `qwen-tts` service should not download models implicitly during `generate` calls.
- If the requested model snapshot is missing, `generate` should fail fast with a clear error.

Provisioning options (choose one):

1. **Out-of-band provisioning command** (preferred):
   - Provide a single-purpose “download models into `/models`” action (CLI entrypoint or one-shot container command).
2. **Admin HTTP endpoint** (optional):
   - An authenticated `/admin/download` endpoint for controlled provisioning.
   - Keep this out of the critical path for demo runs.

## API Contract (Minimal and Stable)

The service should be boring and predictable. Start with synchronous endpoints returning JSON + a path to a WAV written in `/outputs`.

Endpoints:

- `GET /health`
- `POST /generate/custom`
- `POST /generate/design`
- Optional (gated): `POST /generate/clone`
- Optional: `POST /speakers` (only if it’s stable and cheap; otherwise hardcode speakers in your demo script)

Request fields (conceptual):

- `text` (required)
- `model` (required; must point at a pre-provisioned snapshot under `/models`)
- `output` (optional; otherwise service decides output name deterministically)
- `speaker` (custom mode)
- `instruct` (design mode)
- `reference_audio` + `reference_text` (clone mode; likely multipart)
- `device` (optional; default `cpu` for portability; allow `auto` in non-deterministic benchmarking mode)

Response fields (conceptual):

- `ok: boolean`
- `output_path: string` (relative path under `/outputs`)
- `duration_ms: number`
- `meta`: `model_id`, `device`, `dtype`, `sample_rate_hz`, and timing metrics

## Host Dependency Elimination

This plan is explicitly meant to avoid laptop host installs.

- Install `sox` in the image, not on the host (clone mode needs it; even if clone is gated, baking it in is cheap).
- Keep all caches and models in Docker volumes so the host doesn’t need HF caches or torch caches.

## GPU Strategy (Defer Until After CPU Works)

CPU-first is the default so it runs on laptops.

After the pipeline works end-to-end on CPU:

- Add a GPU profile or alternate image that uses CUDA wheels and the NVIDIA container runtime.
- Keep the API contract identical so the demo pipeline doesn’t care.

## Acceptance Criteria

- `docker compose --profile voiceover up qwen-tts` starts on a laptop with no host installs beyond Docker.
- A single `custom` generation request produces a WAV in `/outputs` and returns `duration_ms`.
- Demo runs are offline-deterministic:
  - no model downloads during generation;
  - missing model snapshot causes a clear failure.
- Clone mode is disabled by default and requires explicit enablement plus a provided reference audio file (and still works without host `sox` installs).

## Open Questions

- Should the service always write to `/outputs` (path-returning API), or should it stream audio bytes (larger payloads but fewer shared volumes)?
- Do you need `/outputs` browsing/streaming endpoints for debugging, or is that out of scope for the demo pipeline?
- What is the minimal set of model snapshots you will pre-provision for the demo (custom/design only first, clone later)?
