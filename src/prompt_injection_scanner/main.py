"""FastAPI application setup with API versioning."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .api.swagger_config import custom_openapi_schema
from .api.v1 import router as v1_router
from .api.v1.handlers import ScanHandlerV1
from .api.versioning import (
    VersionConfig,
    VersionInfo,
    determine_api_version,
    validate_api_version,
)
from .config import get_config
from .factory import create_scanner
from .learning import initialize_feedback_loop
from .stages.vector import VectorStage
from .vector_db.factory import create_vector_db

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - setup and teardown."""
    logger.info("scanner_startup")

    # Initialize components
    config = get_config()

    # Initialize vector database if enabled
    vector_db = None
    if hasattr(config, "vector_db_enabled") and config.vector_db_enabled:
        vector_db_type = getattr(config, "vector_db_type", "memory")
        vector_db_url = getattr(config, "vector_db_url", None)
        vector_db = create_vector_db(vector_db_type, vector_db_url)
        logger.info("vector_db_initialized", type=vector_db_type)

    # Create scanner with vector database
    scanner = create_scanner(vector_db)

    # Initialize feedback loop if vector database is available
    feedback_loop = None
    if vector_db:
        vector_stage = VectorStage(vector_db)
        feedback_loop = initialize_feedback_loop(vector_db, vector_stage)
        logger.info("feedback_loop_initialized")

    # Create versioned handlers
    app.state.v1_handler = ScanHandlerV1(scanner)
    app.state.config = config
    app.state.scanner = scanner
    app.state.vector_db = vector_db
    app.state.feedback_loop = feedback_loop

    yield

    # Cleanup
    if vector_db:
        await vector_db.close()

    logger.info("scanner_shutdown")


# Create FastAPI app with comprehensive OpenAPI documentation
app = FastAPI(
    title="Prompt Injection Scanner API",
    description="""
    🛡️ **Defensive Security Tool for AI Applications**
    
    A sophisticated 3-stage ML-powered pipeline for detecting prompt injection vulnerabilities:
    
    ## 🔍 **Detection Pipeline**
    
    1. **Heuristic Stage** (~2ms): Fast regex pattern matching with 115+ rules
    2. **Vector Similarity** (~25ms): Semantic search using sentence transformers 
    3. **LLM Guardian** (~200ms): AI analysis with structured output validation
    
    ## 🎯 **Key Features**
    
    - **Risk Scoring**: Nuanced 0-100 risk assessment instead of binary pass/fail
    - **API Versioning**: Clean v1 API with backward compatibility
    - **Production Ready**: Docker deployment with monitoring and health checks
    - **ML-Powered**: 115+ training examples with continuous learning
    - **Extensible**: Configurable patterns and pluggable vector databases
    
    ## 🔧 **Supported Integrations**
    
    - **Vector Databases**: ChromaDB, Milvus, Pinecone, Weaviate, Memory
    - **AI Models**: OpenAI GPT-4, Anthropic Claude, Google Gemini (via Pydantic AI)
    - **Deployment**: Docker Compose, Kubernetes, cloud platforms
    
    ## 🚀 **Getting Started**
    
    1. Try the `/v1/scan` endpoint with a test prompt
    2. Check `/v1/health` for system status
    3. Explore `/v1/patterns/` for rule management
    4. Use `/v1/training/` for ML dataset management
    
    ---
    **⚠️ Security Notice**: This tool is designed for defensive security research and protection.
    """,
    version="0.1.0",
    contact={"name": "Security Team", "email": "security@yourcompany.com"},
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://scanner.yourcompany.com", "description": "Production server"},
    ],
    openapi_tags=[
        {
            "name": "v1",
            "description": "Version 1 API endpoints - Current stable API",
        },
        {
            "name": "scanning",
            "description": "Core prompt injection detection functionality",
        },
        {
            "name": "patterns",
            "description": "Pattern management for heuristic detection rules",
        },
        {
            "name": "training",
            "description": "Training dataset management for ML model improvement",
        },
        {
            "name": "feedback",
            "description": "Feedback system for continuous learning and model optimization",
        },
        {
            "name": "health",
            "description": "System health checks and monitoring endpoints",
        },
        {
            "name": "admin",
            "description": "Administrative functions and system management",
        },
    ],
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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
    """Get v1 scan handler from app state."""
    return app.state.v1_handler


# Override the dependency in v1 router
v1_router.dependency_overrides[v1_router.get_scan_handler] = get_v1_handler

# Include versioned routers
app.include_router(v1_router)

# Set custom OpenAPI schema
app.openapi = lambda: custom_openapi_schema(app)


# Root endpoints
@app.get("/")
async def root():
    """Root endpoint - redirect to latest API version."""
    return RedirectResponse(url="/v1/health")


@app.get("/version", response_model=VersionInfo)
async def version_info() -> VersionInfo:
    """Get API version information."""
    config = VersionConfig()
    return VersionInfo(
        current_version=config.current.value,
        supported_versions=[v.value for v in config.supported],
        deprecated_versions=[v.value for v in config.deprecated],
        sunset_dates=config.sunset_dates,
    )


# Legacy endpoints (redirect to v1)
@app.get("/health")
async def legacy_health_check():
    """Legacy health check - redirects to v1."""
    return RedirectResponse(url="/v1/health")


@app.get("/health/detailed")
async def legacy_detailed_health_check():
    """Legacy detailed health check."""
    return {
        "status": "healthy",
        "service": "prompt-injection-scanner",
        "version": "0.1.0",
        "api_version": "legacy",
        "message": "Use /v1/health for current API",
        "components": {
            "heuristic_stage": "healthy",
            "vector_stage": (
                "healthy" if app.state.config.vector_db_enabled else "disabled"
            ),
            "guardian_stage": "healthy",
        },
    }


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint - can be enhanced with Prometheus."""
    return {
        "service": "prompt-injection-scanner",
        "version": "0.1.0",
        "requests_total": 0,  # Would track in production
        "errors_total": 0,
        "avg_response_time_ms": 0.0,
        "api_versions": {"v1": {"requests": 0, "errors": 0}},
    }


# Middleware for API versioning
@app.middleware("http")
async def version_middleware(request: Request, call_next):
    """Middleware to handle API versioning and add version headers."""
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
        log_level="info",
    )
