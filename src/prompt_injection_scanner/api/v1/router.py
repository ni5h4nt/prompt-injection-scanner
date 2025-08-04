"""v1 API router with versioned endpoints
"""


import structlog
from fastapi import APIRouter, Depends

from ..versioning import (
    VersionConfig,
    VersionInfo,
)
from .feedback import feedback_router
from .handlers import ScanHandlerV1
from .models import (
    BatchScanRequest,
    BatchScanResponse,
    HealthResponse,
    ScanRequest,
    ScanResponse,
)
from .patterns import patterns_router
from .training import training_router

logger = structlog.get_logger(__name__)

# Create v1 router with comprehensive OpenAPI documentation
router = APIRouter(
    prefix="/v1",
    tags=["v1", "scanning"],
    responses={
        400: {
            "description": "Bad Request - Invalid input parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid request format or missing required fields"
                    }
                }
            },
        },
        422: {
            "description": "Validation Error - Request data validation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "prompt"],
                                "msg": "field required",
                                "type": "value_error.missing",
                            }
                        ]
                    }
                }
            },
        },
        500: {
            "description": "Internal Server Error - System malfunction",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Internal processing error. Please try again or contact support."
                    }
                }
            },
        },
    },
)


def get_scan_handler() -> ScanHandlerV1:
    """Dependency to get scan handler - will be overridden in main app"""
    # This will be replaced with proper dependency injection in main.py
    from ...factory import create_scanner

    scanner = create_scanner()
    return ScanHandlerV1(scanner)


@router.post(
    "/scan",
    response_model=ScanResponse,
    tags=["scanning"],
    summary="🔍 Scan Prompt for Injection Attacks",
    description="""
    **Analyze a single prompt for potential injection vulnerabilities using our 3-stage ML pipeline.**
    
    ### 🔄 **Processing Pipeline**
    
    1. **Heuristic Stage** (~2ms): Fast pattern matching against 115+ known attack signatures
    2. **Vector Similarity** (~25ms): Semantic analysis using sentence transformers  
    3. **LLM Guardian** (~200ms): AI-powered analysis with structured validation
    
    ### 📊 **Risk Assessment**
    
    Returns a **nuanced risk score (0-100)** instead of binary pass/fail:
    - **0-30**: Low risk - Allow with monitoring
    - **31-60**: Medium risk - Allow with validation  
    - **61-85**: High risk - Block with human review
    - **86-100**: Critical risk - Block immediately
    
    ### 🎯 **Response Features**
    
    - **Stage Breakdown**: Individual results from each detection stage
    - **Threat Categorization**: Specific attack types identified
    - **Security Recommendations**: Actionable mitigation steps
    - **Optional Reasoning**: Detailed explanation when `include_reasoning=true`
    
    ### 💡 **Usage Tips**
    
    - Enable `include_reasoning` for debugging and analysis
    - Use `context` for user tracking and audit trails  
    - Monitor `confidence` scores for model performance
    """,
    responses={
        200: {
            "description": "Successful scan with risk assessment",
            "content": {
                "application/json": {
                    "examples": {
                        "benign_prompt": {
                            "summary": "Benign prompt example",
                            "value": {
                                "risk_score": 15,
                                "risk_level": "low",
                                "confidence": 0.95,
                                "flags": [],
                                "threat_types": [],
                                "recommendations": ["Continue monitoring"],
                                "processing_time_ms": 27,
                                "request_id": "req-benign-123",
                            },
                        },
                        "malicious_prompt": {
                            "summary": "Malicious prompt detected",
                            "value": {
                                "risk_score": 95,
                                "risk_level": "critical",
                                "confidence": 0.97,
                                "flags": [
                                    "instruction_override",
                                    "vector_match",
                                    "llm_malicious",
                                ],
                                "threat_types": [
                                    "system_manipulation",
                                    "information_extraction",
                                ],
                                "recommendations": [
                                    "Block this request immediately",
                                    "Log incident for security review",
                                    "Consider user account investigation",
                                ],
                                "processing_time_ms": 234,
                                "request_id": "req-malicious-456",
                            },
                        },
                    }
                }
            },
        }
    },
)
async def scan_prompt(
    request: ScanRequest, handler: ScanHandlerV1 = Depends(get_scan_handler)
) -> ScanResponse:
    """🔍 **Scan a single prompt for injection attacks**

    Processes the input through our 3-stage detection pipeline and returns
    a comprehensive risk assessment with actionable recommendations.
    """
    return await handler.scan_prompt(request)


@router.post(
    "/batch",
    response_model=BatchScanResponse,
    tags=["scanning"],
    summary="⚡ Batch Scan Multiple Prompts",
    description="""
    **Process multiple prompts efficiently with concurrent scanning and comprehensive error handling.**
    
    ### 🚀 **Performance Features**
    
    - **Concurrent Processing**: Multiple prompts analyzed simultaneously
    - **Batch Optimization**: Shared vector database connections and model loading
    - **Error Isolation**: Individual prompt failures don't affect the entire batch
    - **Progress Tracking**: Real-time status updates for large batches
    
    ### 📦 **Input Format**
    
    Submit an array of prompts with optional individual settings:
    ```json
    {
      "prompts": [
        "First prompt to analyze",
        "Second prompt to check"
      ],
      "include_reasoning": false,
      "context": {"batch_id": "batch-123"}
    }
    ```
    
    ### 📊 **Response Structure**
    
    Returns individual results for each prompt plus batch-level statistics:
    - **Individual Results**: Complete scan results for each prompt
    - **Batch Metrics**: Processing time, success rate, error summary
    - **Request Tracking**: Unique IDs for audit and debugging
    
    ### 💡 **Best Practices**
    
    - Limit batches to 100 prompts for optimal performance
    - Use `context` for batch tracking and user attribution
    - Monitor batch `processing_time_ms` for performance tuning
    - Handle partial failures gracefully in your application
    """,
    responses={
        200: {
            "description": "Batch processing completed (may include partial failures)",
            "content": {
                "application/json": {
                    "example": {
                        "results": [
                            {
                                "risk_score": 15,
                                "risk_level": "low",
                                "confidence": 0.95,
                                "flags": [],
                                "request_id": "batch-item-1",
                            },
                            {
                                "risk_score": 85,
                                "risk_level": "high",
                                "confidence": 0.92,
                                "flags": ["instruction_override"],
                                "request_id": "batch-item-2",
                            },
                        ],
                        "batch_stats": {
                            "total_prompts": 2,
                            "successful_scans": 2,
                            "failed_scans": 0,
                            "avg_risk_score": 50.0,
                            "processing_time_ms": 145,
                        },
                        "request_id": "batch-abc123",
                    }
                }
            },
        }
    },
)
async def batch_scan(
    request: BatchScanRequest, handler: ScanHandlerV1 = Depends(get_scan_handler)
) -> BatchScanResponse:
    """⚡ **Batch scan multiple prompts with concurrent processing**

    Efficiently processes multiple prompts in parallel with comprehensive
    error handling and batch-level metrics.
    """
    return await handler.batch_scan(request)


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="🏥 System Health Check",
    description="""
    **Comprehensive health status for all system components and dependencies.**
    
    ### 🔍 **Component Monitoring**
    
    - **Heuristic Stage**: Pattern matching engine status
    - **Vector Database**: Connection and search capability
    - **LLM Guardian**: AI model availability and response time
    - **Training Data**: Dataset integrity and loading status
    - **Feedback System**: Learning pipeline operational status
    
    ### 📊 **Status Levels**
    
    - **healthy**: Component fully operational
    - **degraded**: Component working with reduced performance  
    - **unhealthy**: Component experiencing issues
    - **disabled**: Component intentionally disabled
    
    ### 🚨 **Monitoring Integration**
    
    This endpoint is designed for:
    - Load balancer health checks
    - Kubernetes liveness/readiness probes
    - Monitoring system alerts (Prometheus, DataDog, etc.)
    - Automated deployment verification
    """,
    responses={
        200: {
            "description": "System health status retrieved successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "healthy": {
                            "summary": "All systems operational",
                            "value": {
                                "status": "healthy",
                                "service": "prompt-injection-scanner",
                                "version": "0.1.0",
                                "components": {
                                    "heuristic_stage": "healthy",
                                    "vector_stage": "healthy",
                                    "guardian_stage": "healthy",
                                    "training_data": "healthy",
                                    "feedback_system": "healthy",
                                },
                                "uptime_seconds": 3600,
                                "request_id": "health-check-123",
                            },
                        },
                        "degraded": {
                            "summary": "Some components degraded",
                            "value": {
                                "status": "degraded",
                                "service": "prompt-injection-scanner",
                                "version": "0.1.0",
                                "components": {
                                    "heuristic_stage": "healthy",
                                    "vector_stage": "degraded",
                                    "guardian_stage": "healthy",
                                    "training_data": "healthy",
                                    "feedback_system": "unhealthy",
                                },
                                "uptime_seconds": 1800,
                                "request_id": "health-check-456",
                            },
                        },
                    }
                }
            },
        },
        503: {
            "description": "Service unavailable - critical components failing",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "service": "prompt-injection-scanner",
                        "error": "Critical component failure detected",
                    }
                }
            },
        },
    },
)
async def health_check(
    handler: ScanHandlerV1 = Depends(get_scan_handler),
) -> HealthResponse:
    """🏥 **Comprehensive system health check**

    Returns detailed status information for all system components,
    designed for monitoring and automated health verification.
    """
    return await handler.health_check()


# Include sub-routers
router.include_router(patterns_router)
router.include_router(feedback_router)
router.include_router(training_router)


@router.get("/version", response_model=VersionInfo)
async def version_info() -> VersionInfo:
    """Get API version information
    """
    config = VersionConfig()
    return VersionInfo(
        current_version=config.current.value,
        supported_versions=[v.value for v in config.supported],
        deprecated_versions=[v.value for v in config.deprecated],
        sunset_dates=config.sunset_dates,
    )
