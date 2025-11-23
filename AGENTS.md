# Agent Guide

This document is the canonical guide for all AI coding assistants working in this repository. It consolidates the most accurate guidance from prior assistant-specific files.

## How to Use This Guide
- **Start with guardrails**: Focus on the Agent Protocol section for interaction patterns
- **Use as reference**: Dip into specific sections as needed, don't read end-to-end
- **Follow the workflows**: Use the Workflow Examples for common task patterns
- **Check decisions**: Use the checklists and decision trees for validation
- **Stay current**: This doc evolves with the codebase - check git history for changes

**For detailed technical specifications**, see the project README and linked documentation. This guide focuses on AI agent interaction patterns and workflows.

## Documentation Principles
- **Start with guardrails, not manuals**: This doc focuses on boundaries and patterns, not exhaustive instructions
- **Evolution over completeness**: This guide grows with discovered issues and patterns
- **Point, don't embed**: References to external docs are preferred over duplicating content
- **Provide alternatives**: Never say "never X" without suggesting "prefer Y instead"
- **Use as forcing function**: Simplicity in this doc encourages simplicity in the codebase

## What This Project Is
- BahnVision delivers Munich public transit data via a FastAPI backend and a React + TypeScript frontend.
- Backend emphasizes predictable latency using Valkey-backed caching with single-flight locks, stale fallbacks, and circuit-breaker behavior.
- Persistence uses async SQLAlchemy with a shared engine; observability exports Prometheus metrics.

## Core References
- Main README: [README.md](README.md) for complete project overview and current implementation
- Backend spec: [docs/tech-spec.md](docs/tech-spec.md)
- Frontend docs hub: [frontend/docs/README.md](frontend/docs/README.md)
- Compose topology and envs: [docker-compose.yml](docker-compose.yml)
- Backend docs hub: [backend/docs/README.md](backend/docs/README.md)

## Agent Protocol

### Core Interaction Patterns
- **Read before changing**: Always understand existing code before proposing modifications
- **Small, verifiable plans**: Break complex tasks into incremental, testable changes
- **Ask clarifying questions early**: When requirements are ambiguous, ask before implementing
- **Propose, don't assume**: Present options for technical decisions with trade-offs

### Decision-Making Guidelines
- **Autonomous decisions**: Code style, bug fixes, test additions, straightforward refactors
- **Ask before changing**: Architecture modifications, API changes, new dependencies, database schema changes
- **Always propose**: Security changes, performance optimizations that change behavior, major feature additions

### Change Proposal Structure
When proposing changes, include:
1. **Problem statement**: What issue does this solve?
2. **Proposed solution**: High-level approach and implementation plan
3. **Impact assessment**: Files affected, testing requirements, breaking changes
4. **Alternative approaches**: Considered options and why this approach was chosen

### Communication Style
- **Be specific**: Reference exact file paths and line numbers when discussing issues
- **Provide examples**: Show code examples for complex changes
- **Include testing plan**: Describe how changes will be validated
- **Document trade-offs**: Explain why certain approaches were chosen over alternatives

### File Operation Guidelines
- **Use `Grep` for content search**: When looking for specific code patterns or text
- **Use `Glob` for file discovery**: When finding files by name patterns or structure
- **Use `Read` for targeted file reading**: When you know the specific file path
- **Use `Task` for complex exploration**: When searching requires multiple rounds or context-building
- **See complete decision tree**: Refer to Agent-Specific Operations section for detailed tool selection

### Error Handling and Escalation
- **Try local resolution first**: Attempt to fix issues using available tools and context
- **Document failed attempts**: Explain what you tried and why it didn't work
- **Escalate with context**: When stuck, provide full context about the problem and attempted solutions

## Agent-Specific Operations

### Change Impact Assessment Framework
Before making changes, assess:
1. **Scope**: How many files/components are affected?
2. **Criticality**: Does this affect core functionality (API, cache, database)?
3. **Dependencies**: Will this require new packages or modify existing ones?
4. **Testing**: What tests need to be added or updated?
5. **Documentation**: What documentation needs updating?

### Code Review Guidelines for AI-Generated Changes
- **Security review**: Check for injection vulnerabilities, authentication issues, data exposure
- **Performance impact**: Consider caching implications, database query efficiency, memory usage
- **Error handling**: Ensure proper error propagation and user feedback
- **Logging and observability**: Add appropriate metrics and logging for new functionality
- **Testing coverage**: Verify unit, integration, and E2E test coverage

### Tool Selection Decision Tree
```
Need to find something?
├─ Know exact file path → Use Read
├─ Know file pattern/name → Use Glob
├─ Searching for code/content → Use Grep
└─ Complex, multi-step search → Use Task with Explore agent

Need to modify code?
├─ Simple fix → Edit directly
├─ Multiple related changes → Use TodoWrite to track
└─ Complex refactoring → Plan first, then implement

Need to run commands?
├─ Git operations → Use Bash directly
├─ Package management → Use Bash with verification steps
├─ Testing → Use Bash, then analyze results
└─ Long-running processes → Use Bash with background flag
```

### Package and Dependency Management
- **Always verify current versions**: Use `pip index versions <package>` or `npm view <package> versions`
- **Pin exact versions**: Use `==` for Python, `package@version` for npm
- **Check compatibility**: Verify new dependencies don't conflict with existing ones
- **Update requirements files**: Keep [`backend/requirements.txt`](backend/requirements.txt) and [`frontend/package.json`](frontend/package.json) in sync
- **Test after updates**: Run full test suite after dependency changes

### Database Operations
- **Always use migrations**: Never modify database schema directly
- **Test migrations**: Verify migrations work in development before production
- **Backup before major changes**: Use database dumps before schema modifications
- **Consider data impact**: Understand how changes affect existing data
- **Rollback planning**: Have rollback strategy for each migration

## Repository Structure
- Backend runtime: [`backend/app`](backend/app)
  - [`main.py`](backend/app/main.py) — FastAPI app factory with lifespan management
  - [`api/`](backend/app/api/) — versioned routes under `/api/v1`, metrics exporter
    - [`api/v1/endpoints/`](backend/app/api/v1/endpoints/) — actual endpoint implementations
    - [`api/v1/shared/`](backend/app/api/v1/shared/) — shared caching patterns and utilities
    - [`api/metrics.py`](backend/app/api/metrics.py) — exposes Prometheus metrics at `/metrics`
  - [`services/`](backend/app/services/) — shared infrastructure (e.g., MVG client, cache service)
  - [`models/`](backend/app/models/) — Pydantic schemas for request/response validation
  - [`persistence/`](backend/app/persistence/) — async SQLAlchemy models (stations) and repositories
  - [`core/config.py`](backend/app/core/config.py) — Pydantic settings, Valkey/database config
  - [`jobs/`](backend/app/jobs/) — standalone scripts (cache warmup)
- Frontend runtime: [`frontend/`](frontend/)
  - [`src/components`](frontend/src/components), [`src/pages`](frontend/src/pages), [`src/hooks`](frontend/src/hooks), [`src/services`](frontend/src/services)
  - Vite + React 19 + TypeScript; Tailwind; TanStack Query; React Router

## Running the Stack
- Local (backend):
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r backend/requirements.txt`
  - `uvicorn app.main:app --reload --app-dir backend` → `http://127.0.0.1:8000`
- Local (frontend):
  - `npm install`
  - `npm run dev` → `http://127.0.0.1:5173`
- Docker Compose (recommended):
  - `docker compose up --build`
  - Compose starts a short-lived `cache-warmup` service first (`python -m app.jobs.cache_warmup`) so Valkey/Postgres already contain the MVG station catalog before the backend handles traffic.
  - Backend at `http://127.0.0.1:8000`; Frontend at `http://127.0.0.1:3000`
- Database connectivity:
  - Default `DATABASE_URL` (local): `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`
  - Compose overrides target the `postgres` service per `docker-compose.yml`

## Backend Architecture
- Dependency injection: use FastAPI dependencies for services and repositories.
- Service layer:
  - `services/mvg_client.py` wraps MVG API requests and instruments latency/metrics; maps results and errors.
  - `services/cache.py` provides Valkey-backed cache with:
    - Single-flight locking to prevent stampedes
    - Stale reads with background refresh
    - Circuit breaker fallback to in-process store on failures
- Cache configuration (selected env vars):
  - `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`, `_WAIT_SECONDS`, `_RETRY_DELAY_SECONDS`
  - `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`
  - Endpoint-specific TTLs (e.g., `MVG_*_CACHE_TTL_SECONDS`, `*_STALE_TTL_SECONDS`)
  - Cache warmup knobs: `CACHE_WARMUP_DEPARTURE_STATIONS`, `CACHE_WARMUP_DEPARTURE_LIMIT`, `CACHE_WARMUP_DEPARTURE_OFFSET_MINUTES`
- Persistence layer (`backend/app/persistence/`):
  - Async SQLAlchemy models and repositories (stations actively used)
  - Additional models exist for future analytics features (not currently implemented)
  - `core/database.py` provides a shared async engine
- HTTP schemas in `backend/app/models/` enforce request/response contracts.

## Frontend Architecture
- Stack: React 19, TypeScript, Vite, Tailwind, TanStack Query, React Router.
- Structure: components, pages, hooks, and services under `frontend/src`.
- Testing: Vitest, React Testing Library, Playwright; MSW for API mocking.

## Observability
- Metrics (Prometheus):
  - `bahnvision_cache_events_total{cache,event}` — events include examples like `hit`, `miss`, `stale_return`, `lock_timeout`, `not_found`, `refresh_success`, `refresh_error`, `refresh_skip_hit`, `refresh_not_found`, `background_not_found`, `background_lock_timeout`.
  - `bahnvision_cache_refresh_seconds{cache}` — histogram of cache refresh latency.
  - `bahnvision_mvg_requests_total{endpoint,result}` — MVG client request outcomes.
  - `bahnvision_mvg_request_seconds{endpoint}` — histogram of MVG client request latency.
- Response headers: `X-Cache-Status` indicates cache path (`hit`, `miss`, `stale`, `stale-refresh`).
- SLAs (targets): cache hit ratio >70%, MVG P95 latency <750ms.

## Coding Style
- Python: PEP 8, 4-space indentation, snake_case modules.
- Prefer typed function signatures; use Pydantic for validation.
- Keep services stateless; co-locate HTTP schemas with consuming routes.
- Frontend: standard React/TS practices; organize by components/pages/hooks/services.

## Testing Guidelines
- Backend:
  - Use `pytest`; place tests under `backend/tests/` mirroring `app/` structure.
  - Test FastAPI routes via `TestClient`; override dependencies as needed.
  - Use in-memory doubles (e.g., `FakeValkey`, `FakeMVGClient`) to keep tests deterministic.
  - Note: No coverage tools currently configured (pytest only)
- Frontend:
  - Unit/integration via Vitest + React Testing Library
  - E2E via Playwright; use MSW for API mocking
  - Coverage tools available via `npm run test:coverage`

## Workflow Examples

### Debugging Cache Issues
**Scenario**: API responses are slow or cache metrics show low hit ratio

**Steps**:
1. Check cache metrics: `curl http://localhost:8000/metrics | grep bahnvision_cache`
2. Inspect cache keys: `redis-cli KEYS "*"` (or Valkey equivalent)
3. Check for stale keys: `redis-cli KEYS "*:stale"`
4. Verify TTL settings: Check environment variables `CACHE_*_TTL_SECONDS`
5. Review cache configuration in [`backend/app/core/config.py`](backend/app/core/config.py)
6. Test cache behavior manually using the endpoints
7. Check single-flight lock timeouts if seeing cache stampedes

**Common fixes**:
- Adjust TTL values for specific endpoints
- Tune single-flight lock timeout settings
- Verify cache key generation logic
- Check circuit breaker configuration

### Adding a New API Endpoint
**Scenario**: Need to add a new endpoint for fetching nearby stations

**Workflow**:
1. **Research**: Examine existing endpoints in [`backend/app/api/v1/endpoints/`](backend/app/api/v1/endpoints/)
2. **Plan**: Define request/response schemas, caching strategy, error handling
3. **Implement**:
   - Add Pydantic models in [`backend/app/models/`](backend/app/models/)
   - Create endpoint implementation in appropriate endpoints file
   - Add caching using existing patterns from `api/v1/shared/`
   - Add metrics if needed
4. **Test**:
   - Write unit tests in `backend/tests/`
   - Test manually with `uvicorn` running locally
   - Verify cache behavior and metrics
5. **Document**: Update any relevant documentation

### Frontend Feature Addition Workflow
**Scenario**: Add a new component to display real-time departures

**Workflow**:
1. **Explore**: Understand existing component patterns in [`frontend/src/components/`](frontend/src/components/)
2. **Plan**: Define component structure, state management, API integration
3. **Implement**:
   - Create component in appropriate directory
   - Add hooks if needed in [`frontend/src/hooks/`](frontend/src/hooks/)
   - Update routing if new page required
   - Add API service calls in [`frontend/src/services/`](frontend/src/services/)
4. **Test**:
   - Add unit tests with Vitest + React Testing Library
   - Test with MSW mocks for API calls
   - Run E2E tests with Playwright
5. **Validate**: Check TypeScript types, run `npm run build`

### Database Migration Workflow
**Scenario**: Add new field to Station model

**Workflow**:
1. **Analyze**: Understand current model in [`backend/app/persistence/models/`](backend/app/persistence/models/)
2. **Plan migration**: Create Alembic migration for backward-compatible changes
3. **Implement**:
   - Generate migration: `alembic revision --autogenerate -m "add field to stations"`
   - Review generated migration SQL
   - Update SQLAlchemy model
4. **Test**:
   - Apply migration locally: `alembic upgrade head`
   - Test backward compatibility
   - Verify rollback: `alembic downgrade -1`
5. **Validate**: Test with existing application code

### Performance Investigation Workflow
**Scenario**: API endpoints are slow, need to identify bottleneck

**Steps**:
1. **Check metrics**: Look at Prometheus metrics for request latency
2. **Profile code**: Add timing logs around suspected slow operations
3. **Check cache**: Verify cache hit ratios and refresh times
4. **Database queries**: Review SQLAlchemy query patterns and N+1 issues
5. **MVG API calls**: Check external API response times
6. **Test with load**: Use simple load testing to reproduce issue

**Common optimizations**:
- Add missing cache layers
- Optimize database queries with proper joins
- Implement request deduplication
- Add circuit breaker for external calls

### Dependency Update Workflow
**Scenario**: Update FastAPI to latest version

**Steps**:
1. **Check compatibility**: Read FastAPI release notes for breaking changes
2. **Verify current version**: Check `backend/requirements.txt`
3. **Test update**: Update version locally, run tests
4. **Check dependent packages**: Verify other packages still compatible
5. **Update requirements**: Pin new exact version
6. **Run full test suite**: Ensure no regressions
7. **Test manually**: Verify application starts and functions correctly

## Dependency & Versioning Policy
- Verify current versions (e.g., `pip index versions <pkg>`); do not guess based on memory.
- Pin exact versions (use `==`) for reproducible builds.
- Typical workflow:
  - Check versions → update `backend/requirements.txt` → install → verify.

## Security & Configuration
- Store secrets (Valkey URLs, API tokens) in environment variables or a local `.env` kept out of version control.
- Document non-default runtime options (e.g., custom `DATABASE_URL`, cache TTL overrides) in PRs.
 - Valkey settings accept legacy `REDIS_*` env var aliases for backward compatibility.

## Commit & PR Guidelines
- Follow Conventional Commits (e.g., `feat:`, `fix:`, `docs:`, `build:`).
- Keep subjects concise; include a body for multi-file changes.
- Reference related issues; highlight config/schema updates and any manual steps.
- Include screenshots or sample responses for endpoint changes.

## Common Gotchas
- Cache writes populate both Valkey and fallback store (circuit-breaker resilience).
- Single-flight lock timeouts may need tuning for long refreshes.
- Stale cache keys use `:stale` suffix; inspect both `{key}` and `{key}:stale`.
- SQLAlchemy engine disposal occurs in app lifespan; tests must respect this lifecycle.
- Transport type enum casing: API accepts case-insensitive input; MVG uses uppercase.
- Database models include complex analytics schemas (DepartureObservation, WeatherObservation, RouteSnapshot) but only Station models are actively used in current implementation.
- Architecture documentation in archive/ folder shows planned features not yet implemented.

## Knowledge Management Framework

### Decision Boundaries
**Autonomous decisions (no approval needed)**:
- Code style fixes and formatting improvements
- Bug fixes that don't change API contracts
- Adding or improving tests for existing functionality
- Documentation updates that clarify existing behavior
- Performance optimizations that don't change observable behavior
- Dependency updates for patch versions (e.g., 1.2.3 → 1.2.4)

**Requires proposal (wait for approval)**:
- New API endpoints or modification of existing ones
- Database schema changes or new migrations
- New dependencies or major version updates
- Changes to caching strategy or architecture
- Security-related changes
- Breaking changes to existing functionality

**Always ask first**:
- Changes that might affect data integrity
- Modifications to deployment or infrastructure
- Changes that could impact existing SLAs
- Removal of existing features or deprecations

### Context Gathering Strategy
**When starting a task**:
1. **Quick assessment**: Use `Glob` and `Grep` to understand the scope
2. **Deep dive**: Read key files to understand current implementation
3. **Check dependencies**: Look for related code that might be affected
4. **Review tests**: Understand existing test coverage and patterns

**When encountering ambiguity**:
1. **Search for similar patterns**: Use `Grep` to find how similar problems were solved
2. **Check documentation**: Look for existing patterns in docs
3. **Examine git history**: Use `git log` to understand recent changes
4. **Ask clarifying questions**: Present specific alternatives with trade-offs

### Change Documentation Requirements
**For every change**:
- **Commit message**: Follow conventional commits with clear description
- **Code comments**: Add comments for non-obvious implementation details
- **Update documentation**: Update relevant README sections or API docs
- **Test updates**: Add or modify tests to cover new functionality

**For significant changes**:
- **Design rationale**: Document why specific approaches were chosen
- **Migration guide**: If there are breaking changes, provide migration steps
- **Performance impact**: Document any performance implications
- **Security considerations**: Note any security-related changes

### Learning and Improvement Process
**After completing complex tasks**:
1. **Document lessons learned**: What worked well, what didn't
2. **Update AGENTS.md**: Add new patterns or gotchas discovered
3. **Suggest improvements**: Recommend tooling or process improvements
4. **Share knowledge**: Document new patterns for future reference

**When encountering repeated problems**:
1. **Identify root cause**: Use systematic debugging approach
2. **Document solution**: Create reusable troubleshooting guide
3. **Consider systemic fixes**: Suggest changes to prevent future occurrences
4. **Update documentation**: Ensure solutions are captured for others

### Knowledge Sharing Standards
**Code patterns worth documenting**:
- New architectural patterns or design decisions
- Non-obvious bug fixes or workarounds
- Performance optimization techniques
- Security best practices or improvements
- Testing strategies for complex scenarios

**Communication templates**:
- **Bug reports**: Include steps to reproduce, expected vs actual behavior
- **Feature proposals**: Include problem statement, proposed solution, alternatives
- **Code review requests**: Include summary of changes, testing done, areas needing review
- **Troubleshooting guides**: Include symptoms, diagnosis steps, solutions

## Troubleshooting
- Backend not starting: confirm `DATABASE_URL` and Valkey reachability, then retry.
- Cache behaving unexpectedly: check metrics and `:stale` keys; verify TTL envs.
- Frontend API calls failing: verify `VITE_API_BASE_URL` and CORS; ensure backend is reachable.

## Interactive Checklists

### Pre-Commit Checklist
Before committing any changes, verify:
- [ ] **Code quality**: Code follows project style guidelines
- [ ] **Tests pass**: All relevant tests pass successfully
- [ ] **New tests**: Added tests for new functionality
- [ ] **Documentation**: Updated relevant documentation
- [ ] **No secrets**: No hardcoded credentials or API keys
- [ ] **Dependencies**: Updated requirements files if needed
- [ ] **Breaking changes**: Documented any breaking API changes
- [ ] **Performance**: Considered performance implications
- [ ] **Security**: Reviewed for security issues

### Code Review Checklist
When reviewing changes (your own or others'):
- [ ] **Functionality**: Does the code work as intended?
- [ ] **Tests**: Are tests comprehensive and passing?
- [ ] **Error handling**: Are errors properly handled and logged?
- [ ] **Security**: Are there any security vulnerabilities?
- [ ] **Performance**: Will this impact performance negatively?
- [ ] **Documentation**: Is the code well-documented?
- [ ] **Maintainability**: Is the code easy to understand and modify?
- [ ] **Consistency**: Does it follow existing patterns?

### Deployment Readiness Checklist
Before deploying to production:
- [ ] **All tests pass**: Full test suite is green
- [ ] **Manual testing**: Key functionality tested manually
- [ ] **Performance**: Load testing performed if needed
- [ ] **Security**: Security review completed
- [ ] **Backups**: Database backups verified
- [ ] **Rollback plan**: Rollback strategy documented
- [ ] **Monitoring**: Monitoring and alerting in place
- [ ] **Documentation**: Deployment documentation updated

### Debugging Checklist
When investigating issues:
- [ ] **Reproduce**: Can you consistently reproduce the issue?
- [ ] **Logs**: Check application logs for error messages
- [ ] **Metrics**: Review performance metrics and alerts
- [ ] **Recent changes**: Check recent deployments or code changes
- [ ] **Environment**: Verify environment variables and configuration
- [ ] **Dependencies**: Check for dependency issues or conflicts
- [ ] **External services**: Verify external API/service availability
- [ ] **Isolation**: Can you isolate the problem to a specific component?

## Quick Reference Decision Trees

### "Should I add a test?" Decision Tree
```
Is this new functionality?
├─ Yes → Add unit tests + integration tests
└─ No
   ├─ Is this fixing a bug? → Add regression test
   └─ Is this refactoring? → Ensure existing tests still pass
```

### "Which tool should I use?" Decision Tree
```
Need to find something?
├─ Specific file path → Read
├─ File name pattern → Glob
├─ Code/content search → Grep
└─ Complex exploration → Task with Explore agent

Need to change something?
├─ Single line/fix → Edit directly
├─ Multiple related changes → TodoWrite + Edit
└─ Complex feature → Plan → TodoWrite → Implement

Need to run something?
├─ Quick command → Bash
├─ Long-running process → Bash with background flag
└─ Multiple parallel operations → Multiple Bash calls
```

### "Is this ready for production?" Decision Tree
```
Code complete?
├─ No → Complete development
└─ Yes
   ├─ Tests passing? → Fix failing tests
   └─ Yes
      ├─ Security reviewed? → Complete security review
      └─ Yes
         ├─ Performance tested? → Complete performance testing
         └─ Yes → Ready for deployment
```

### "What documentation is needed?" Decision Tree
```
Type of change?
├─ Bug fix → Update changelog, add comments if complex
├─ New feature → API docs, user docs, changelog
├─ Breaking change → Migration guide, API docs, changelog
└─ Infrastructure → Deploy docs, config examples, runbooks
```

This AGENTS.md is authoritative for all assistants working in this repository.
