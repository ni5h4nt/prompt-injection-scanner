"""Regression smoke test: the FastAPI app imports and registers expected routes.

Guards against the latent DI bug fixed alongside the fastapi/starlette 1.x bump
(main.py used `v1_router.dependency_overrides[v1_router.get_scan_handler]`,
where both `dependency_overrides` and `get_scan_handler` were not attributes of
APIRouter). The app failed at import-time on every FastAPI version until that
fix; this test ensures it never silently regresses.
"""

from prompt_injection_scanner.main import app
from prompt_injection_scanner.api.v1.router import get_scan_handler


def test_app_registers_expected_routes():
    paths = {getattr(route, "path", None) for route in app.routes}
    for expected in ("/", "/v1/scan", "/v1/health"):
        assert expected in paths, f"missing route: {expected}"


def test_scan_handler_dependency_is_overridden_at_app_level():
    assert get_scan_handler in app.dependency_overrides
