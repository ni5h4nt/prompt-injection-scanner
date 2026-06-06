# Dependency Code-Migration Design

**Date:** 2026-06-06
**Status:** accepted
**Branch:** `feat/dep-code-migration` (stacked on `chore/dependency-security-updates`, PR #2)

## What

Clear the remaining Dependabot advisories that require source changes (not just lockfile bumps):

- **`pydantic-ai`** high — GHSA-2jrp-274c-jhv3 — needs 1.x (0.4.11 pinned)
- **`starlette`** high + medium — pulled by `fastapi`; needs starlette ≥0.49.1 (1.x), which requires `fastapi` ≥ ~0.136

## Why

These were carved out of PR #2 (pure lockfile bumps) because they break source code. The `fastapi` bump also surfaces a **pre-existing latent bug**: `main.py:171` references `v1_router.dependency_overrides`, but `dependency_overrides` is a `FastAPI`-app attribute, not an `APIRouter` one. The app entrypoint does not import today on any fastapi version; no test exercises it.

`torch` / `transformers` advisories are explicitly **out of scope** — no stable patched release exists (transformers' fix is a pre-release; torch is transitively capped).

## Scope (two source files + deps)

### 1. `src/prompt_injection_scanner/stages/guardian.py` — pydantic-ai 0.4→1.x

- Line 44: `result_type=SecurityAnalysis` → `output_type=SecurityAnalysis`
- Line 70: `result.data` → `result.output`
- `system_prompt=` kwarg: verify 1.x still accepts it; rename to `instructions=` only if rejected.

Verified against pydantic-ai 1.x docs: `output_type`, `.output`, `deps_type`, and `'openai:gpt-4'`-style model strings are all current. `.run(prompt, deps=...)` async invocation is unchanged.

### 2. `src/prompt_injection_scanner/main.py` — fastapi 0.115→~0.136 / starlette 1.x

- Fix line 171:
  `v1_router.dependency_overrides[v1_router.get_scan_handler] = get_v1_handler`
  → `app.dependency_overrides[v1_router.get_scan_handler] = get_v1_handler`
  The override must live on the app and be keyed by the same `get_scan_handler` callable the endpoints reference via `Depends(get_scan_handler)`.
- Verify these survive starlette 1.x (expected no-ops — all stable APIs): `lifespan` async context manager, `app.openapi = lambda: custom_openapi_schema(app)`, `RedirectResponse`, `CORSMiddleware`.

### 3. Dependencies

Targeted `poetry update fastapi starlette pydantic-ai` (full `poetry update` fails locally building chromadb's sdist — environment toolchain bug, not a conflict). Update `pyproject.toml` pins:
- `fastapi = "==0.115.14"` → permissive range allowing ≥0.136
- `pydantic-ai = "==0.4.11"` → `^1.0` (or the resolved 1.x)

## Testing (minimal smoke tests — no API key required)

Create `tests/unit/`:
- `test_app_import.py` — the FastAPI `app` imports without error and registers expected routes (`/v1/scan`, `/v1/health`, `/`). This is the regression guard for the DI bug.
- `test_guardian_construct.py` — `GuardianStage` instantiates and its pydantic-ai `Agent` builds with `output_type=SecurityAnalysis` (constructing the agent does NOT call the LLM, so no key needed).

Guardian *end-to-end* (actual LLM call) needs an API key and is therefore not run in CI; the construction test is the verifiable proxy.

## Out of scope

- `torch` / `transformers` (no stable fix)
- Any broader refactor of the DI pattern, the Guardian decorator stack, or the API surface
- A full test suite (only the two regression smoke tests above)

## Verification (acceptance)

1. `poetry run python -c "import prompt_injection_scanner.main"` succeeds (app imports).
2. `poetry run pytest tests/unit/` passes.
3. Locked versions: `pydantic-ai` ≥1.0, `starlette` ≥0.49.1, `fastapi` ≥0.136.
4. `poetry check` consistent.

## PR strategy

New branch `feat/dep-code-migration` off `chore/dependency-security-updates`; stacked PR targeting `chore/dependency-security-updates`, keeping PR #2 a pure lockfile change.
