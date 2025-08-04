"""v1 Feedback API endpoints for continuous learning
"""

from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...learning import FeedbackLoop, get_feedback_loop

logger = structlog.get_logger(__name__)

# Create feedback router
feedback_router = APIRouter(
    prefix="/feedback",
    tags=["feedback"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        422: {"description": "Validation Error"},
    },
)


class FeedbackRequest(BaseModel):
    """Request model for providing feedback"""

    text: str = Field(
        ..., min_length=1, max_length=4096, description="The original prompt text"
    )
    predicted_risk: int = Field(
        ..., ge=0, le=100, description="Risk score that was predicted"
    )
    predicted_label: str = Field(
        ..., pattern="^(malicious|benign)$", description="Label that was predicted"
    )
    actual_label: str = Field(
        ...,
        pattern="^(malicious|benign)$",
        description="Correct label (human verified)",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in the feedback"
    )
    user_id: Optional[str] = Field(default=None, description="Optional user identifier")


class FalsePositiveRequest(BaseModel):
    """Request model for reporting false positives"""

    text: str = Field(
        ..., min_length=1, max_length=4096, description="The incorrectly flagged prompt"
    )
    predicted_risk: int = Field(
        ..., ge=0, le=100, description="Risk score that was predicted"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in the feedback"
    )
    user_id: Optional[str] = Field(default=None, description="Optional user identifier")


class FalseNegativeRequest(BaseModel):
    """Request model for reporting false negatives"""

    text: str = Field(
        ..., min_length=1, max_length=4096, description="The missed malicious prompt"
    )
    predicted_risk: int = Field(
        ..., ge=0, le=100, description="Risk score that was predicted"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in the feedback"
    )
    user_id: Optional[str] = Field(default=None, description="Optional user identifier")


class FeedbackResponse(BaseModel):
    """Response model for feedback operations"""

    success: bool
    message: str
    feedback_id: Optional[str] = None


def get_feedback_loop_dependency() -> FeedbackLoop:
    """Dependency to get feedback loop instance"""
    feedback_loop = get_feedback_loop()
    if not feedback_loop:
        raise HTTPException(
            status_code=503,
            detail="Feedback system not initialized. Enable vector similarity search to use feedback.",
        )
    return feedback_loop


@feedback_router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    feedback_request: FeedbackRequest,
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop_dependency),
):
    """Submit feedback about a prediction

    This helps the system learn from its mistakes and improve accuracy over time.
    """
    try:
        await feedback_loop.record_feedback(
            text=feedback_request.text,
            predicted_risk=feedback_request.predicted_risk,
            predicted_label=feedback_request.predicted_label,
            actual_label=feedback_request.actual_label,
            confidence=feedback_request.confidence,
            user_id=feedback_request.user_id,
        )

        feedback_type = (
            "correct"
            if feedback_request.predicted_label == feedback_request.actual_label
            else "incorrect"
        )

        logger.info(
            "feedback_submitted_via_api",
            feedback_type=feedback_type,
            predicted_label=feedback_request.predicted_label,
            actual_label=feedback_request.actual_label,
            predicted_risk=feedback_request.predicted_risk,
        )

        return FeedbackResponse(
            success=True,
            message=f"Feedback recorded successfully. Type: {feedback_type}",
            feedback_id=f"fb_{hash(feedback_request.text)}",
        )

    except Exception as e:
        logger.error("feedback_submission_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to record feedback")


@feedback_router.post("/false-positive", response_model=FeedbackResponse)
async def report_false_positive(
    request: FalsePositiveRequest,
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop_dependency),
):
    """Report a false positive (benign prompt incorrectly flagged as malicious)

    This helps reduce false alarms by teaching the system what benign content looks like.
    """
    try:
        await feedback_loop.record_false_positive(
            text=request.text,
            predicted_risk=request.predicted_risk,
            confidence=request.confidence,
        )

        logger.info(
            "false_positive_reported_via_api",
            predicted_risk=request.predicted_risk,
            user_id=request.user_id,
        )

        return FeedbackResponse(
            success=True,
            message="False positive reported. This will help improve accuracy.",
            feedback_id=f"fp_{hash(request.text)}",
        )

    except Exception as e:
        logger.error("false_positive_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to report false positive")


@feedback_router.post("/false-negative", response_model=FeedbackResponse)
async def report_false_negative(
    request: FalseNegativeRequest,
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop_dependency),
):
    """Report a false negative (malicious prompt that was missed)

    This helps catch similar attacks in the future by expanding the malicious pattern database.
    """
    try:
        await feedback_loop.record_false_negative(
            text=request.text,
            predicted_risk=request.predicted_risk,
            confidence=request.confidence,
        )

        logger.info(
            "false_negative_reported_via_api",
            predicted_risk=request.predicted_risk,
            user_id=request.user_id,
        )

        return FeedbackResponse(
            success=True,
            message="False negative reported. This will help catch similar attacks.",
            feedback_id=f"fn_{hash(request.text)}",
        )

    except Exception as e:
        logger.error("false_negative_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to report false negative")


@feedback_router.get("/metrics", response_model=Dict[str, Any])
async def get_performance_metrics(
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop_dependency),
):
    """Get performance metrics based on feedback data

    Returns accuracy, precision, recall, and F1 score based on user feedback.
    """
    try:
        metrics = await feedback_loop.get_performance_metrics()

        logger.info(
            "performance_metrics_requested",
            accuracy=metrics.get("accuracy", 0),
            total_feedback=metrics.get("total_feedback", 0),
        )

        return metrics

    except Exception as e:
        logger.error("performance_metrics_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@feedback_router.get("/threshold-suggestions", response_model=Dict[str, Any])
async def get_threshold_suggestions(
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop_dependency),
):
    """Get suggested threshold adjustments based on feedback patterns

    Analyzes false positive/negative rates to suggest optimal threshold values.
    """
    try:
        suggestions = await feedback_loop.suggest_threshold_adjustments()

        logger.info(
            "threshold_suggestions_requested",
            suggestions_count=len(suggestions.get("suggestions", [])),
        )

        return suggestions

    except Exception as e:
        logger.error("threshold_suggestions_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail="Failed to get threshold suggestions"
        )


@feedback_router.post("/force-update", response_model=Dict[str, Any])
async def force_learning_update(
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop_dependency),
):
    """Force immediate processing of feedback buffer

    Normally feedback is processed in batches. This endpoint forces immediate processing
    of any pending feedback for testing or urgent updates.
    """
    try:
        buffer_size_before = len(feedback_loop.feedback_buffer)
        await feedback_loop.force_learning_update()

        logger.info(
            "forced_learning_update_completed", processed_items=buffer_size_before
        )

        return {
            "success": True,
            "message": "Learning update completed",
            "processed_items": buffer_size_before,
        }

    except Exception as e:
        logger.error("forced_learning_update_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to force learning update")


@feedback_router.get("/export", response_model=Dict[str, Any])
async def export_feedback_data(
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop_dependency),
):
    """Export feedback data for external analysis

    Returns all feedback data in the current buffer for analysis or backup.
    """
    try:
        feedback_data = await feedback_loop.export_feedback_data()

        logger.info("feedback_data_exported", items_count=len(feedback_data))

        return {
            "feedback_data": feedback_data,
            "count": len(feedback_data),
            "exported_at": feedback_loop.stats.get("last_learning_update"),
        }

    except Exception as e:
        logger.error("feedback_data_export_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to export feedback data")
