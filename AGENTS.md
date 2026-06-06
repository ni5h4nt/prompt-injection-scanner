# Agent Guidelines

## Project Context

**Project:** prompt-injection-scanner
**Language:** Python 3.12+
**Framework:** FastAPI
**Test Framework:** pytest

## Development Workflow

Use the **casef** skill for all feature development. This ensures:
- Dependency-aware planning with execution waves
- Mandatory quality gates per phase
- Microcommits with conventional commit messages
- Small, reviewable PRs

All plans MUST use the CASEF plan format with `[depends: X]` and `[est: ~N lines]` metadata on every phase.

## Code Standards

### Naming Conventions
- snake_case for all Python identifiers and JSON field names
- PascalCase for classes (Pydantic models, SQLAlchemy models)
- UPPER_SNAKE_CASE for constants

### Architecture Rules
- No business logic in route handlers — delegate to service functions
- All database access through async sessions, never in routes
- API versioning via URL path: /api/v1/...
- Errors follow RFC 7807 Problem Details format
- Response envelope: { "data": ..., "meta": ... } for collections

### Testing Requirements
- Unit tests for all service/business logic functions
- Integration tests for API endpoints (httpx AsyncClient or test client)
- Minimum 80% coverage
- Tests follow Arrange-Act-Assert pattern

## API Conventions

- API versioning via URL path: /api/v1/...
- Errors follow RFC 7807 Problem Details format
- Response envelope for collections: { "data": [...], "meta": {...} }
- snake_case for JSON field names
- Dates in ISO 8601 UTC
- Pagination: default 25, max 100, enforced server-side
- X-Request-Id generated and returned in every response
- Auth via Authorization header or X-API-Key (never in URL)
- CORS with specific origins (no wildcard in production)

## PR Guidelines

- Max PR size: 400 lines (hard limit 600)
- Branch naming: `feat/`, `fix/`, `refactor/`, `chore/`
- Squash merge preferred

## Tooling

| Tool | Use |
|---|---|
| Package manager | `uv` |
| Init project | `uv init --no-readme` |
| Add dependency | `uv add <pkg>` |
| Add dev dependency | `uv add --dev <pkg>` |
| Run command | `uv run <cmd>` |
| Formatter | `ruff` |
| Linter | `ruff` |
| Type checker | `mypy` |
| Test runner | `pytest` |

**Always use these tools.** Do not substitute with alternatives (e.g., do not use pip if uv is specified, do not use npm if pnpm is specified).
