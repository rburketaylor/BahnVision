# BahnVision Frontend Planning Index

This directory captures high-level planning artifacts for the upcoming BahnVision frontend implementation. Each document focuses on a specific concern so the team can iterate on scope and sequencing before writing production code.

- `architecture.md` – proposed technical stack, application layering, data flows, and integration touchpoints.
- `ux-flows.md` – prioritized user journeys, wireflow notes, and state considerations for core screens.
- `api-integration.md` – REST contract summary across `/api/v1/health`, `/api/v1/mvg/departures`, `/api/v1/mvg/stations/search`, `/api/v1/mvg/routes/plan`, and `/metrics`, including request parameters and response payload outlines for frontend consumption.
- `testing.md` – testing strategy spanning unit/UI/integration coverage, mock guidelines, and CI hooks.
- `observability.md` – client-side telemetry, error reporting, and operational feedback loops that complement backend metrics.
- `roadmap.md` – phase plan with milestones, dependencies, and delivery sequencing.
- `adr.md` – initial architectural decision record capturing the rationale for the chosen stack and API usage patterns.

Update these files as the frontend design evolves so implementation work stays aligned with backend capabilities described in `backend/docs/tech-spec.md`.
