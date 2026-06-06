# Dependency Code-Migration Implementation Plan

> **For Claude:** REQUIRED: Use the casef skill to execute this plan.

**Goal:** Clear the `pydantic-ai` and `starlette` Dependabot advisories by bumping to 1.x / fastapi ~0.136 and adapting the two source files that break, with smoke tests guarding the result.

**Architecture:** Two isolated source edits (`guardian.py` for pydantic-ai, `main.py` for the FastAPI DI fix) behind a single targeted dependency bump, plus two no-API-key smoke tests. No refactor beyond what the bumps require.

**Tech Stack:** Python 3.12, Poetry, FastAPI/Starlette, pydantic-ai, pytest.

---

## Phase 1: Bump dependencies [depends: none] [est: ~6 lines]

**Files:**
- Modify: `pyproject.toml`
- Modify: `poetry.lock`

**Step 1:** In `pyproject.toml`, change `fastapi = "==0.115.14"` → `fastapi = ">=0.136.0,<1.0.0"` and `pydantic-ai = "==0.4.11"` → `pydantic-ai = "^1.0"`.

**Step 2:** Resolve with a targeted update (avoids the chromadb sdist build that breaks full `poetry update`):
```bash
poetry update fastapi starlette pydantic-ai pydantic-ai-slim
```

**Step 3:** Verify resolved versions: `pydantic-ai` ≥1.0, `starlette` ≥0.49.1, `fastapi` ≥0.136; run `poetry check`.

**Step 4: Commit**
```bash
git add pyproject.toml poetry.lock
git commit -m "build(deps): bump fastapi/starlette and pydantic-ai to 1.x

Phase 1/4 of dep-code-migration"
```

---

## Phase 2: Migrate Guardian to pydantic-ai 1.x [depends: 1] [est: ~3 lines]

**Files:**
- Modify: `src/prompt_injection_scanner/stages/guardian.py`

**Step 1:** Line 44: `result_type=SecurityAnalysis` → `output_type=SecurityAnalysis`.

**Step 2:** Line 70: `result.data` → `result.output`.

**Step 3:** Confirm `system_prompt=` still constructs under 1.x:
```bash
poetry run python -c "import sys; sys.path.insert(0,'src'); from prompt_injection_scanner.stages.guardian import GuardianStage; GuardianStage()" 
```
If it raises on `system_prompt`, rename the kwarg to `instructions=`.

**Step 4: Commit**
```bash
git add src/prompt_injection_scanner/stages/guardian.py
git commit -m "fix(guardian): migrate pydantic-ai result_type/data to output_type/output

Phase 2/4 of dep-code-migration"
```

---

## Phase 3: Fix app DI wiring for FastAPI/Starlette 1.x [depends: 1] [est: ~2 lines]

**Files:**
- Modify: `src/prompt_injection_scanner/main.py`

**Step 1:** Line 171: change `v1_router.dependency_overrides[v1_router.get_scan_handler] = get_v1_handler` → `app.dependency_overrides[v1_router.get_scan_handler] = get_v1_handler`.

**Step 2:** Verify the app imports and routes register:
```bash
poetry run python -c "import sys; sys.path.insert(0,'src'); import prompt_injection_scanner.main as m; print(len(m.app.routes), 'routes')"
```

**Step 3:** Spot-check that `lifespan`, `app.openapi`, `RedirectResponse`, and CORS are unchanged (no edits expected — stable APIs).

**Step 4: Commit**
```bash
git add src/prompt_injection_scanner/main.py
git commit -m "fix(api): move dependency override to app level for starlette 1.x

Phase 3/4 of dep-code-migration"
```

---

## Phase 4: Add smoke tests and verify [depends: 2, 3] [est: ~45 lines]

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_app_import.py`
- Create: `tests/unit/test_guardian_construct.py`

**Step 1:** `test_app_import.py` — assert `prompt_injection_scanner.main.app` imports and that `/v1/scan`, `/v1/health`, and `/` paths are registered in `app.routes`.

**Step 2:** `test_guardian_construct.py` — assert `GuardianStage()` instantiates and that building its pydantic-ai `Agent` with `output_type=SecurityAnalysis` does not raise (no LLM call, no API key).

**Step 3:** Run and confirm green:
```bash
poetry run pytest tests/unit/ -v
```

**Step 4: Commit**
```bash
git add tests/
git commit -m "test: add smoke tests for app import and guardian construction

Phase 4/4 of dep-code-migration"
```
