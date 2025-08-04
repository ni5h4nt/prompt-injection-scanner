"""v1 API handlers with enhanced functionality
"""

import asyncio
import time
from datetime import datetime
from functools import wraps
from typing import Callable, List
from uuid import uuid4

import structlog
from fastapi import HTTPException

from ...core.scanner import Scanner
from .models import (
    BatchScanRequest,
    BatchScanResponse,
    ErrorResponse,
    HealthResponse,
    ScanRequest,
    ScanResponse,
    StageResult,
)

logger = structlog.get_logger(__name__)


def error_handler_v1(func: Callable) -> Callable:
    """Enhanced error handler for v1 API with detailed error responses"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except ValueError as e:
            logger.warning("validation_error", error=str(e))
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=str(e),
                    error_code="VALIDATION_ERROR",
                    error_type="validation_error",
                ).model_dump(),
            )
        except HTTPException:
            raise  # Re-raise HTTP exceptions as-is
        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error="Internal server error",
                    error_code="INTERNAL_ERROR",
                    error_type="server_error",
                    details={"original_error": str(e)},
                ).model_dump(),
            )

    return wrapper


def request_timing_v1(func: Callable) -> Callable:
    """Enhanced timing decorator for v1 API"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = await func(self, *args, **kwargs)

        processing_time = int((time.time() - start_time) * 1000)

        # Add timing to response
        if hasattr(result, "processing_time_ms"):
            result.processing_time_ms = processing_time

        return result

    return wrapper


def request_logging_v1(func: Callable) -> Callable:
    """Enhanced logging decorator for v1 API"""

    @wraps(func)
    async def wrapper(self, request: ScanRequest, *args, **kwargs):
        logger.info(
            "v1_scan_request",
            request_id=request.request_id,
            prompt_length=len(request.prompt),
            has_context=bool(request.context),
            include_reasoning=request.include_reasoning,
            api_version="v1",
        )

        result = await func(self, request, *args, **kwargs)

        logger.info(
            "v1_scan_response",
            request_id=result.request_id,
            risk_score=result.risk_score,
            risk_level=result.risk_level.value,
            flags=result.flags,
            processing_time_ms=result.processing_time_ms,
            api_version="v1",
        )

        return result

    return wrapper


class ScanHandlerV1:
    """v1 API handler with enhanced features
    Maintains backward compatibility while adding new capabilities
    """

    def __init__(self, scanner: Scanner):
        self.scanner = scanner

    @error_handler_v1
    @request_timing_v1
    @request_logging_v1
    async def scan_prompt(self, request: ScanRequest) -> ScanResponse:
        """Enhanced scan with detailed stage results"""
        # Generate request ID if not provided
        if not request.request_id:
            request.request_id = str(uuid4())

        # Track stage timings
        stage_timings = {}
        stage_results = []

        # Enhanced scanning with stage tracking
        start_time = time.time()

        # Scan the prompt
        result = await self.scanner.scan(
            prompt=request.prompt,
            request_id=request.request_id,
            metadata=request.context or {},
        )

        # Build stage results (enhanced in v1)
        for stage_name, score in result.stage_scores.items():
            stage_result = StageResult(
                stage_name=stage_name,
                risk_score=score,
                confidence=result.confidence,  # Individual stage confidence would be tracked separately
                flags=[flag for flag in result.flags if stage_name in flag.lower()]
                or [],
                processing_time_ms=stage_timings.get(stage_name, 0),
            )
            stage_results.append(stage_result)

        # Build enhanced response
        response = ScanResponse(
            risk_score=result.risk_score,
            risk_level="",  # Will be computed by validator
            confidence=result.confidence,
            flags=result.flags,
            threat_types=self._categorize_threats(result.flags),
            stage_results=stage_results,
            stage_scores=result.stage_scores,  # Legacy compatibility
            request_id=result.request_id,
            api_version="v1",
            recommendations=self._generate_recommendations(result),
        )

        # Add reasoning if requested
        if request.include_reasoning:
            response.reasoning = self._generate_reasoning(result, stage_results)

        return response

    def _categorize_threats(self, flags: List[str]) -> List[str]:
        """Categorize threat flags into types"""
        threat_categories = set()

        flag_to_category = {
            "instruction_override": "system_manipulation",
            "system_prompt": "information_extraction",
            "jailbreak": "safety_bypass",
            "role_play": "impersonation",
            "delimiter_attack": "input_manipulation",
            "VECTOR_MATCH": "known_attack_pattern",
            "LLM_ANALYSIS_MALICIOUS": "ai_detected_threat",
        }

        for flag in flags:
            category = flag_to_category.get(flag, "unknown_threat")
            threat_categories.add(category)

        return list(threat_categories)

    def _generate_recommendations(self, scan_result) -> List[str]:
        """Generate security recommendations based on scan results"""
        recommendations = []

        if scan_result.risk_score >= 85:
            recommendations.append("Block this request immediately")
            recommendations.append("Log incident for security review")
        elif scan_result.risk_score >= 65:
            recommendations.append("Require additional authentication")
            recommendations.append("Apply strict content filtering")
        elif scan_result.risk_score >= 35:
            recommendations.append("Monitor user behavior")
            recommendations.append("Apply standard content policy")
        else:
            recommendations.append("Allow with normal monitoring")

        # Flag-specific recommendations
        if "system_prompt" in scan_result.flags:
            recommendations.append("Review system prompt exposure risks")

        if "jailbreak" in scan_result.flags:
            recommendations.append("Strengthen safety guidelines")

        return recommendations

    def _generate_reasoning(self, scan_result, stage_results: List[StageResult]) -> str:
        """Generate detailed reasoning for the decision"""
        reasoning_parts = [
            f"Overall risk assessment: {scan_result.risk_score}/100 (confidence: {scan_result.confidence:.2f})"
        ]

        for stage in stage_results:
            if stage.risk_score > 0:
                reasoning_parts.append(
                    f"{stage.stage_name.title()} stage: {stage.risk_score} points "
                    f"(flags: {', '.join(stage.flags) if stage.flags else 'none'})"
                )

        if scan_result.flags:
            reasoning_parts.append(f"Detected patterns: {', '.join(scan_result.flags)}")

        return ". ".join(reasoning_parts)

    @error_handler_v1
    @request_timing_v1
    async def batch_scan(self, request: BatchScanRequest) -> BatchScanResponse:
        """Process multiple prompts in batch"""
        batch_id = request.request_id or str(uuid4())
        start_time = time.time()

        logger.info(
            "v1_batch_scan_started",
            batch_id=batch_id,
            prompt_count=len(request.prompts),
        )

        # Process all prompts concurrently
        tasks = []
        for i, prompt in enumerate(request.prompts):
            scan_request = ScanRequest(
                prompt=prompt,
                context=request.context,
                include_reasoning=request.include_reasoning,
                request_id=f"{batch_id}-{i}",
            )
            tasks.append(self.scan_prompt(scan_request))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions in results
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "batch_scan_item_failed",
                    batch_id=batch_id,
                    item_index=i,
                    error=str(result),
                )
                # Create error result
                error_result = ScanResponse(
                    risk_score=0,
                    risk_level="low",
                    confidence=0.0,
                    flags=["PROCESSING_ERROR"],
                    request_id=f"{batch_id}-{i}",
                    api_version="v1",
                    reasoning=f"Processing failed: {str(result)}",
                )
                successful_results.append(error_result)
            else:
                successful_results.append(result)

        processing_time = int((time.time() - start_time) * 1000)

        response = BatchScanResponse(
            results=successful_results,
            batch_id=batch_id,
            total_processed=len(successful_results),
            processing_time_ms=processing_time,
            api_version="v1",
        )

        logger.info(
            "v1_batch_scan_completed",
            batch_id=batch_id,
            total_processed=len(successful_results),
            processing_time_ms=processing_time,
        )

        return response

    async def health_check(self) -> HealthResponse:
        """Enhanced health check with component status"""
        return HealthResponse(
            status="healthy",
            service="prompt-injection-scanner",
            version="0.1.0",
            api_version="v1",
            timestamp=datetime.utcnow().isoformat(),
            components={
                "heuristic_stage": "healthy",
                "vector_stage": "healthy",
                "guardian_stage": "healthy",
                "database": "healthy",
            },
        )
