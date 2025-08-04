"""Clean API handlers with decorator-based error handling and logging
"""

import time
from functools import wraps
from typing import Callable, Dict

import structlog
from fastapi import HTTPException

from ..core.scanner import Scanner
from .models import ScanRequest, ScanResponse

logger = structlog.get_logger(__name__)


def error_handler(func: Callable) -> Callable:
    """Decorator for clean error handling - abstracts exception complexity"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValueError as e:
            logger.warning("validation_error", error=str(e))
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")

    return wrapper


def request_timing(func: Callable) -> Callable:
    """Decorator for request timing - abstracts timing complexity"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)

        # Add timing to response if it's a ScanResponse
        if isinstance(result, ScanResponse):
            result.processing_time_ms = int((time.time() - start_time) * 1000)

        return result

    return wrapper


def request_logging(func: Callable) -> Callable:
    """Decorator for request/response logging"""

    @wraps(func)
    async def wrapper(request: ScanRequest, *args, **kwargs):
        logger.info(
            "scan_request",
            request_id=request.request_id,
            prompt_length=len(request.prompt),
            has_context=bool(request.context),
        )

        result = await func(request, *args, **kwargs)

        logger.info(
            "scan_response",
            request_id=result.request_id,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            flags=result.flags,
        )

        return result

    return wrapper


class ScanHandler:
    """Clean API handler with decorator-driven cross-cutting concerns
    Follows single responsibility principle
    """

    def __init__(self, scanner: Scanner):
        self.scanner = scanner

    @error_handler  # Handle exceptions cleanly
    @request_timing  # Add timing information
    @request_logging  # Log requests/responses
    async def scan_prompt(self, request: ScanRequest) -> ScanResponse:
        """Simple scan handler - decorators handle complexity
        KISS: Just coordinate between request/response and scanner
        """
        # Scan the prompt
        result = await self.scanner.scan(
            prompt=request.prompt,
            request_id=request.request_id,
            metadata=request.context,
        )

        # Convert to API response format
        return ScanResponse(
            risk_score=result.risk_score,
            confidence=result.confidence,
            flags=result.flags,
            stage_scores=result.stage_scores,
            request_id=result.request_id,
            risk_level="",  # Will be computed by validator
        )

    async def health_check(self) -> Dict[str, str]:
        """Simple health check - YAGNI"""
        return {"status": "healthy", "service": "prompt-injection-scanner"}
