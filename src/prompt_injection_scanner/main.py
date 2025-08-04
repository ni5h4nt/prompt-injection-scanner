"""
FastAPI application setup with API versioning
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import structlog

from .api.versioning import determine_api_version, validate_api_version, APIVersion, VersionInfo, VersionConfig
from .api.v1 import router as v1_router
from .api.v1.handlers import ScanHandlerV1
from .factory import create_scanner
from .config import get_config

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - setup and teardown"""
    logger.info("scanner_startup")
    
    # Initialize components
    config = get_config()
    scanner = create_scanner()
    
    # Create versioned handlers
    app.state.v1_handler = ScanHandlerV1(scanner)
    app.state.config = config
    app.state.scanner = scanner
    
    yield
    
    logger.info("scanner_shutdown")


# Create FastAPI app with versioning
app = FastAPI(
    title="Prompt Injection Scanner API",
    description="Defensive security tool for detecting prompt injection attacks",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency override for v1 handler
def get_v1_handler() -> ScanHandlerV1:
    """Get v1 scan handler from app state"""
    return app.state.v1_handler


# Override the dependency in v1 router
v1_router.dependency_overrides[v1_router.get_scan_handler] = get_v1_handler

# Include versioned routers
app.include_router(v1_router)


# Root endpoints
@app.get("/")
async def root():
    """Root endpoint - redirect to latest API version"""
    return RedirectResponse(url="/v1/health")


@app.get("/version", response_model=VersionInfo)
async def version_info() -> VersionInfo:
    """
    Get API version information
    """
    config = VersionConfig()
    return VersionInfo(
        current_version=config.current.value,
        supported_versions=[v.value for v in config.supported],
        deprecated_versions=[v.value for v in config.deprecated],
        sunset_dates=config.sunset_dates
    )


# Legacy endpoints (redirect to v1)
@app.get("/health")
async def legacy_health_check():
    """Legacy health check - redirects to v1"""
    return RedirectResponse(url="/v1/health")


@app.get("/health/detailed") 
async def legacy_detailed_health_check():
    """Legacy detailed health check"""
    return {
        "status": "healthy",
        "service": "prompt-injection-scanner", 
        "version": "0.1.0",
        "api_version": "legacy",
        "message": "Use /v1/health for current API",
        "components": {
            "heuristic_stage": "healthy",
            "vector_stage": "healthy" if app.state.config.vector_db_enabled else "disabled",
            "guardian_stage": "healthy",
        }
    }


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint - can be enhanced with Prometheus"""
    return {
        "service": "prompt-injection-scanner",
        "version": "0.1.0",
        "requests_total": 0,  # Would track in production
        "errors_total": 0,
        "avg_response_time_ms": 0.0,
        "api_versions": {
            "v1": {"requests": 0, "errors": 0}
        }
    }


# Middleware for API versioning
@app.middleware("http")
async def version_middleware(request: Request, call_next):
    """Middleware to handle API versioning and add version headers"""
    
    # Determine API version
    api_version = determine_api_version(request)
    
    # Validate version
    try:
        validate_api_version(api_version)
    except HTTPException as e:
        return e
    
    # Add version to request state
    request.state.api_version = api_version
    
    # Process request
    response = await call_next(request)
    
    # Add version headers to response
    response.headers["API-Version"] = api_version.value
    response.headers["API-Supported-Versions"] = "v1"
    
    return response


if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    uvicorn.run(
        "prompt_injection_scanner.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info"
    )