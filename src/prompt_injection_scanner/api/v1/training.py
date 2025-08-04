"""v1 Training data management API endpoints
"""

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...data import ThreatCategory, TrainingExample, get_training_dataset
from ...data.training_dataset import PromptInjectionDataset

logger = structlog.get_logger(__name__)

# Create training router with comprehensive documentation
training_router = APIRouter(
    prefix="/training",
    tags=["training"],
    responses={
        400: {
            "description": "Bad Request - Invalid training data or parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid training example format or missing required fields"
                    }
                }
            },
        },
        404: {
            "description": "Training example not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Training example at index 42 not found"}
                }
            },
        },
        422: {
            "description": "Validation Error - Training data validation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid label or category for training example"
                    }
                }
            },
        },
    },
)


class TrainingExampleRequest(BaseModel):
    """Request model for adding training examples"""

    text: str = Field(..., min_length=1, max_length=4096, description="The prompt text")
    label: str = Field(
        ..., pattern="^(malicious|benign)$", description="Label (malicious or benign)"
    )
    category: str = Field(..., description="Threat category")
    severity: str = Field(
        default="medium",
        pattern="^(low|medium|high|critical)$",
        description="Severity level",
    )
    confidence: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Confidence in the label"
    )
    source: str = Field(default="api", description="Source of the example")


class TrainingExampleResponse(BaseModel):
    """Response model for training example operations"""

    success: bool
    message: str
    example_id: Optional[str] = None


class TrainingStatsResponse(BaseModel):
    """Response model for training statistics"""

    total_examples: int
    malicious_examples: int
    benign_examples: int
    categories: Dict[str, int]
    severities: Dict[str, int]
    high_confidence_examples: int


def get_training_dataset_dependency() -> PromptInjectionDataset:
    """Dependency to get training dataset"""
    return get_training_dataset()


@training_router.get(
    "/stats",
    response_model=TrainingStatsResponse,
    summary="📊 Training Dataset Statistics",
    description="""
    **Get comprehensive statistics about the current training dataset used for ML model training.**
    
    ### 📈 **Dataset Metrics**
    
    - **Total Examples**: Complete count of training examples
    - **Label Distribution**: Malicious vs benign example counts
    - **Category Breakdown**: Examples by threat category (system_override, role_manipulation, etc.)
    - **Severity Levels**: Distribution across low/medium/high/critical severity
    - **Quality Metrics**: High-confidence examples and annotation statistics
    
    ### 🎯 **Use Cases**
    
    - Monitor dataset growth and balance
    - Identify areas needing more training data
    - Track annotation quality over time
    - Validate model training readiness
    
    ### 💡 **Insights**
    
    Use these statistics to:
    - Ensure balanced malicious/benign examples (recommended 60/40 ratio)
    - Identify underrepresented threat categories
    - Monitor high-confidence example growth for model improvements
    """,
    responses={
        200: {
            "description": "Training dataset statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_examples": 115,
                        "malicious_examples": 75,
                        "benign_examples": 40,
                        "categories": {
                            "system_override": 15,
                            "role_manipulation": 15,
                            "information_extraction": 15,
                            "safety_bypass": 15,
                            "input_manipulation": 15,
                        },
                        "severities": {
                            "low": 20,
                            "medium": 35,
                            "high": 40,
                            "critical": 20,
                        },
                        "high_confidence_examples": 95,
                    }
                }
            },
        }
    },
)
async def get_training_stats(
    dataset: PromptInjectionDataset = Depends(get_training_dataset_dependency),
):
    """📊 **Get comprehensive training dataset statistics**

    Returns detailed metrics about the current training dataset including
    distribution, quality, and category breakdowns.
    """
    try:
        data = dataset.to_dict()
        stats = data["stats"]

        # Calculate high confidence examples
        high_conf_count = len(dataset.get_high_confidence_examples(0.9))

        return TrainingStatsResponse(
            total_examples=stats["total_examples"],
            malicious_examples=stats["malicious_examples"],
            benign_examples=stats["benign_examples"],
            categories=stats["categories"],
            severities={
                "low": len(dataset.get_by_severity("low")),
                "medium": len(dataset.get_by_severity("medium")),
                "high": len(dataset.get_by_severity("high")),
                "critical": len(dataset.get_by_severity("critical")),
            },
            high_confidence_examples=high_conf_count,
        )

    except Exception as e:
        logger.error("training_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get training statistics")


@training_router.get("/examples", response_model=List[Dict[str, Any]])
async def list_training_examples(
    label: Optional[str] = Query(
        None, pattern="^(malicious|benign)$", description="Filter by label"
    ),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(
        None, pattern="^(low|medium|high|critical)$", description="Filter by severity"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of examples to return"
    ),
    offset: int = Query(0, ge=0, description="Number of examples to skip"),
    dataset: PromptInjectionDataset = Depends(get_training_dataset_dependency),
):
    """List training examples with optional filtering

    Returns a paginated list of training examples with optional filters.
    """
    try:
        examples = dataset.examples.copy()

        # Apply filters
        if label:
            examples = [ex for ex in examples if ex.label == label]

        if category:
            examples = [ex for ex in examples if ex.category.value == category]

        if severity:
            examples = [ex for ex in examples if ex.severity == severity]

        # Apply pagination
        total = len(examples)
        examples = examples[offset : offset + limit]

        # Convert to dict format
        result = []
        for i, example in enumerate(examples):
            result.append(
                {
                    "id": f"example_{offset + i}",
                    "text": example.text,
                    "label": example.label,
                    "category": example.category.value,
                    "severity": example.severity,
                    "confidence": example.confidence,
                    "source": example.source,
                }
            )

        logger.info(
            "training_examples_listed",
            total=total,
            returned=len(result),
            filters={"label": label, "category": category, "severity": severity},
        )

        return result

    except Exception as e:
        logger.error("list_training_examples_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list training examples")


@training_router.post("/examples", response_model=TrainingExampleResponse)
async def add_training_example(
    request: TrainingExampleRequest,
    dataset: PromptInjectionDataset = Depends(get_training_dataset_dependency),
):
    """Add a new training example

    Adds a new training example to the dataset. This will be used for future ML training.
    Note: This adds to the in-memory dataset. For persistent storage, use the feedback API
    or restart the service after modifying pattern files.
    """
    try:
        # Convert category string to ThreatCategory enum
        try:
            if request.label == "benign":
                category = ThreatCategory.BENIGN
            else:
                # Try to match category string to enum
                category_map = {
                    "system_override": ThreatCategory.SYSTEM_OVERRIDE,
                    "role_manipulation": ThreatCategory.ROLE_MANIPULATION,
                    "information_extraction": ThreatCategory.INFORMATION_EXTRACTION,
                    "safety_bypass": ThreatCategory.SAFETY_BYPASS,
                    "input_manipulation": ThreatCategory.INPUT_MANIPULATION,
                    "benign": ThreatCategory.BENIGN,
                }
                category = category_map.get(
                    request.category.lower(), ThreatCategory.SYSTEM_OVERRIDE
                )
        except Exception:
            category = (
                ThreatCategory.SYSTEM_OVERRIDE
                if request.label == "malicious"
                else ThreatCategory.BENIGN
            )

        # Create training example
        example = TrainingExample(
            text=request.text,
            label=request.label,
            category=category,
            severity=request.severity,
            confidence=request.confidence,
            source=request.source,
        )

        # Add to dataset
        dataset.examples.append(example)
        example_id = f"api_example_{hash(request.text)}"

        logger.info(
            "training_example_added",
            example_id=example_id,
            label=request.label,
            category=category.value,
            severity=request.severity,
        )

        return TrainingExampleResponse(
            success=True,
            message="Training example added successfully",
            example_id=example_id,
        )

    except Exception as e:
        logger.error("add_training_example_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add training example")


@training_router.delete(
    "/examples/{example_index}", response_model=TrainingExampleResponse
)
async def remove_training_example(
    example_index: int,
    dataset: PromptInjectionDataset = Depends(get_training_dataset_dependency),
):
    """Remove a training example by index

    Removes a training example from the dataset by its index position.
    Use GET /training/examples to see indices.
    """
    try:
        if example_index < 0 or example_index >= len(dataset.examples):
            raise HTTPException(
                status_code=404,
                detail=f"Training example at index {example_index} not found",
            )

        removed_example = dataset.examples.pop(example_index)

        logger.info(
            "training_example_removed",
            index=example_index,
            text_preview=removed_example.text[:50] + "...",
            label=removed_example.label,
        )

        return TrainingExampleResponse(
            success=True,
            message=f"Training example at index {example_index} removed successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "remove_training_example_failed", index=example_index, error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to remove training example")


@training_router.put(
    "/examples/{example_index}", response_model=TrainingExampleResponse
)
async def update_training_example(
    example_index: int,
    request: TrainingExampleRequest,
    dataset: PromptInjectionDataset = Depends(get_training_dataset_dependency),
):
    """Update a training example by index

    Updates an existing training example with new values.
    """
    try:
        if example_index < 0 or example_index >= len(dataset.examples):
            raise HTTPException(
                status_code=404,
                detail=f"Training example at index {example_index} not found",
            )

        # Convert category string to enum (same logic as add)
        try:
            if request.label == "benign":
                category = ThreatCategory.BENIGN
            else:
                category_map = {
                    "system_override": ThreatCategory.SYSTEM_OVERRIDE,
                    "role_manipulation": ThreatCategory.ROLE_MANIPULATION,
                    "information_extraction": ThreatCategory.INFORMATION_EXTRACTION,
                    "safety_bypass": ThreatCategory.SAFETY_BYPASS,
                    "input_manipulation": ThreatCategory.INPUT_MANIPULATION,
                    "benign": ThreatCategory.BENIGN,
                }
                category = category_map.get(
                    request.category.lower(), ThreatCategory.SYSTEM_OVERRIDE
                )
        except Exception:
            category = (
                ThreatCategory.SYSTEM_OVERRIDE
                if request.label == "malicious"
                else ThreatCategory.BENIGN
            )

        # Update the example
        old_example = dataset.examples[example_index]
        dataset.examples[example_index] = TrainingExample(
            text=request.text,
            label=request.label,
            category=category,
            severity=request.severity,
            confidence=request.confidence,
            source=request.source,
        )

        logger.info(
            "training_example_updated",
            index=example_index,
            old_label=old_example.label,
            new_label=request.label,
            old_category=old_example.category.value,
            new_category=category.value,
        )

        return TrainingExampleResponse(
            success=True,
            message=f"Training example at index {example_index} updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "update_training_example_failed", index=example_index, error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to update training example")


@training_router.get("/categories", response_model=List[str])
async def get_training_categories():
    """Get all available training categories

    Returns a list of all available threat categories for training examples.
    """
    return [category.value for category in ThreatCategory]


@training_router.post("/export", response_model=Dict[str, Any])
async def export_training_data(
    format: str = Query("json", pattern="^(json|yaml)$", description="Export format"),
    dataset: PromptInjectionDataset = Depends(get_training_dataset_dependency),
):
    """Export training dataset

    Exports the current training dataset in JSON or YAML format.
    """
    try:
        data = dataset.to_dict()

        if format == "yaml":
            import yaml

            content = yaml.dump(data, default_flow_style=False)
            media_type = "application/x-yaml"
        else:
            import json

            content = json.dumps(data, indent=2)
            media_type = "application/json"

        logger.info(
            "training_data_exported", format=format, examples=len(dataset.examples)
        )

        return {
            "success": True,
            "format": format,
            "content": content,
            "stats": data["stats"],
        }

    except Exception as e:
        logger.error("export_training_data_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to export training data")


@training_router.post("/reset", response_model=TrainingExampleResponse)
async def reset_training_data(
    confirm: bool = Query(False, description="Must be true to confirm reset"),
    dataset: PromptInjectionDataset = Depends(get_training_dataset_dependency),
):
    """Reset training dataset to defaults

    WARNING: This will remove all custom training examples and restore the default dataset.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must set confirm=true to reset training data"
        )

    try:
        # Store current count
        old_count = len(dataset.examples)

        # Reset to default dataset
        from ...data.training_dataset import PromptInjectionDataset

        default_dataset = PromptInjectionDataset()
        dataset.examples = default_dataset.examples.copy()

        new_count = len(dataset.examples)

        logger.warning("training_data_reset", old_count=old_count, new_count=new_count)

        return TrainingExampleResponse(
            success=True,
            message=f"Training data reset to defaults. {old_count} -> {new_count} examples",
        )

    except Exception as e:
        logger.error("reset_training_data_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reset training data")
