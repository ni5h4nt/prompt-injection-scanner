"""
v1 API router with versioned endpoints
"""

from fastapi import APIRouter, Depends, Request
from typing import Dict, Any
import structlog

from .models import ScanRequest, ScanResponse, BatchScanRequest, BatchScanResponse, HealthResponse
from .handlers import ScanHandlerV1
from .patterns import patterns_router
from ..versioning import APIVersion, determine_api_version, validate_api_version, VersionInfo, VersionConfig

logger = structlog.get_logger(__name__)

# Create v1 router
router = APIRouter(
    prefix="/v1",
    tags=["v1"],
    responses={
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    }
)


def get_scan_handler() -> ScanHandlerV1:
    """Dependency to get scan handler - will be overridden in main app"""
    # This will be replaced with proper dependency injection in main.py
    from ...factory import create_scanner
    scanner = create_scanner()
    return ScanHandlerV1(scanner)


@router.post("/scan", response_model=ScanResponse)
async def scan_prompt(
    request: ScanRequest,
    handler: ScanHandlerV1 = Depends(get_scan_handler)
) -> ScanResponse:
    """
    Scan a single prompt for injection attacks
    
    **v1 Features:**
    - Detailed stage breakdown
    - Threat categorization
    - Security recommendations
    - Optional reasoning
    """
    return await handler.scan_prompt(request)


@router.post("/batch", response_model=BatchScanResponse)
async def batch_scan(
    request: BatchScanRequest,
    handler: ScanHandlerV1 = Depends(get_scan_handler)
) -> BatchScanResponse:
    """
    Scan multiple prompts in batch
    
    **v1 Features:**
    - Concurrent processing
    - Batch tracking
    - Error handling per item
    """
    return await handler.batch_scan(request)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    handler: ScanHandlerV1 = Depends(get_scan_handler)
) -> HealthResponse:
    """
    Health check endpoint with component status
    """
    return await handler.health_check()


# Include sub-routers
router.include_router(patterns_router)


@router.get("/version", response_model=VersionInfo)
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