"""v1 Pattern management API endpoints
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import structlog
import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from ...patterns import Pattern, PatternManager, PatternSet, PatternStats
from ...patterns.models import PatternType, Severity

logger = structlog.get_logger(__name__)

# Create patterns router with comprehensive documentation
patterns_router = APIRouter(
    prefix="/patterns",
    tags=["patterns"],
    responses={
        400: {
            "description": "Bad Request - Invalid pattern data or parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid pattern format or missing required fields"
                    }
                }
            },
        },
        404: {
            "description": "Pattern not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Pattern with ID 'custom_pattern' not found"}
                }
            },
        },
        422: {
            "description": "Validation Error - Pattern validation failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Pattern regex syntax error or invalid configuration"
                    }
                }
            },
        },
    },
)


class PatternResponse(BaseModel):
    """Response model for pattern operations"""

    success: bool
    message: str
    data: Dict[str, Any] = {}


def get_pattern_manager() -> PatternManager:
    """Dependency to get pattern manager - will be overridden in main app"""
    return PatternManager()


@patterns_router.get("/", response_model=Dict[str, Any])
async def list_patterns(
    category: str = None,
    severity: str = None,
    enabled: bool = None,
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """List all patterns with optional filtering
    """
    try:
        patterns = list(pattern_manager.patterns.values())

        # Apply filters
        if category:
            patterns = [p for p in patterns if p.category == category]

        if severity:
            patterns = [p for p in patterns if p.severity.value == severity]

        if enabled is not None:
            patterns = [p for p in patterns if p.enabled == enabled]

        return {
            "patterns": [p.model_dump() for p in patterns],
            "total": len(patterns),
            "filters": {"category": category, "severity": severity, "enabled": enabled},
        }

    except Exception as e:
        logger.error("list_patterns_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list patterns")


@patterns_router.get("/stats", response_model=PatternStats)
async def get_pattern_stats(
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Get pattern statistics
    """
    try:
        return pattern_manager.get_pattern_stats()
    except Exception as e:
        logger.error("get_pattern_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get pattern statistics")


@patterns_router.get("/sets", response_model=Dict[str, Any])
async def list_pattern_sets(
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """List all pattern sets
    """
    try:
        return {
            "pattern_sets": [
                ps.model_dump() for ps in pattern_manager.pattern_sets.values()
            ],
            "total": len(pattern_manager.pattern_sets),
        }
    except Exception as e:
        logger.error("list_pattern_sets_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list pattern sets")


@patterns_router.get("/sets/{set_name}", response_model=Dict[str, Any])
async def get_pattern_set(
    set_name: str, pattern_manager: PatternManager = Depends(get_pattern_manager)
):
    """Get a specific pattern set
    """
    try:
        if set_name not in pattern_manager.pattern_sets:
            raise HTTPException(
                status_code=404, detail=f"Pattern set '{set_name}' not found"
            )

        pattern_set = pattern_manager.pattern_sets[set_name]
        return {
            "pattern_set": pattern_set.model_dump(),
            "enabled_patterns": len(pattern_set.get_enabled_patterns()),
            "total_patterns": len(pattern_set.patterns),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_pattern_set_failed", set_name=set_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get pattern set")


@patterns_router.post("/sets", response_model=PatternResponse)
async def add_pattern_set(
    pattern_set: PatternSet,
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Add a new pattern set
    """
    try:
        # Validate all patterns in the set
        validation_errors = []
        for pattern in pattern_set.patterns:
            errors = pattern_manager.validate_pattern(pattern)
            if errors:
                validation_errors.extend(
                    [f"Pattern {pattern.id}: {error}" for error in errors]
                )

        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Pattern validation failed",
                    "errors": validation_errors,
                },
            )

        # Add pattern set
        pattern_manager.add_pattern_set(pattern_set)

        logger.info(
            "pattern_set_added",
            name=pattern_set.name,
            patterns=len(pattern_set.patterns),
        )

        return PatternResponse(
            success=True,
            message=f"Pattern set '{pattern_set.name}' added successfully",
            data={
                "name": pattern_set.name,
                "patterns": len(pattern_set.patterns),
                "enabled_patterns": len(pattern_set.get_enabled_patterns()),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_pattern_set_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add pattern set")


@patterns_router.delete("/sets/{set_name}", response_model=PatternResponse)
async def remove_pattern_set(
    set_name: str, pattern_manager: PatternManager = Depends(get_pattern_manager)
):
    """Remove a pattern set
    """
    try:
        if pattern_manager.remove_pattern_set(set_name):
            logger.info("pattern_set_removed", name=set_name)
            return PatternResponse(
                success=True, message=f"Pattern set '{set_name}' removed successfully"
            )
        else:
            raise HTTPException(
                status_code=404, detail=f"Pattern set '{set_name}' not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("remove_pattern_set_failed", set_name=set_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to remove pattern set")


@patterns_router.post("/test", response_model=Dict[str, Any])
async def test_patterns(
    request: Dict[str, str],
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Test text against current patterns
    """
    try:
        text = request.get("text", "")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        matches = pattern_manager.match_patterns(text)
        total_risk = sum(match.get("risk_score", 0) for match in matches)

        return {
            "text": text,
            "matches": matches,
            "total_matches": len(matches),
            "total_risk_score": total_risk,
            "categories": list(set(match["category"] for match in matches)),
            "severities": list(set(match["severity"] for match in matches)),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("test_patterns_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to test patterns")


@patterns_router.post("/reload", response_model=PatternResponse)
async def reload_patterns(
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Reload patterns from configuration files
    """
    try:
        pattern_manager.reload_patterns()
        stats = pattern_manager.get_pattern_stats()

        logger.info("patterns_reloaded", total=stats.total_patterns)

        return PatternResponse(
            success=True,
            message="Patterns reloaded successfully",
            data={
                "total_patterns": stats.total_patterns,
                "pattern_sets": stats.pattern_sets,
            },
        )

    except Exception as e:
        logger.error("reload_patterns_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reload patterns")


@patterns_router.get("/categories", response_model=List[str])
async def get_categories(
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Get all available pattern categories
    """
    try:
        stats = pattern_manager.get_pattern_stats()
        return list(stats.patterns_by_category.keys())
    except Exception as e:
        logger.error("get_categories_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get categories")


@patterns_router.get("/severities", response_model=List[str])
async def get_severities():
    """Get all available severity levels
    """
    return [severity.value for severity in Severity]


@patterns_router.get("/types", response_model=List[str])
async def get_pattern_types():
    """Get all available pattern types
    """
    return [pattern_type.value for pattern_type in PatternType]


# Individual Pattern CRUD Operations


@patterns_router.get("/{pattern_id}", response_model=Dict[str, Any])
async def get_pattern(
    pattern_id: str, pattern_manager: PatternManager = Depends(get_pattern_manager)
):
    """Get a specific pattern by ID
    """
    try:
        pattern = pattern_manager.get_pattern(pattern_id)
        if not pattern:
            raise HTTPException(
                status_code=404, detail=f"Pattern '{pattern_id}' not found"
            )

        return {
            "pattern": pattern.model_dump(),
            "status": "enabled" if pattern.enabled else "disabled",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_pattern_failed", pattern_id=pattern_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get pattern")


@patterns_router.post("/", response_model=PatternResponse)
async def add_pattern(
    pattern: Pattern,
    pattern_set_name: str = "runtime",
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Add a new pattern
    """
    try:
        pattern_manager.add_pattern(pattern, pattern_set_name)

        logger.info(
            "pattern_added_via_api", pattern_id=pattern.id, set_name=pattern_set_name
        )

        return PatternResponse(
            success=True,
            message=f"Pattern '{pattern.id}' added successfully",
            data={
                "pattern_id": pattern.id,
                "pattern_set": pattern_set_name,
                "enabled": pattern.enabled,
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("add_pattern_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add pattern")


@patterns_router.put("/{pattern_id}", response_model=PatternResponse)
async def update_pattern(
    pattern_id: str,
    pattern: Pattern,
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Update an existing pattern
    """
    try:
        if pattern_manager.update_pattern(pattern_id, pattern):
            logger.info("pattern_updated_via_api", pattern_id=pattern_id)

            return PatternResponse(
                success=True,
                message=f"Pattern '{pattern_id}' updated successfully",
                data={"pattern_id": pattern_id, "enabled": pattern.enabled},
            )
        else:
            raise HTTPException(
                status_code=404, detail=f"Pattern '{pattern_id}' not found"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_pattern_failed", pattern_id=pattern_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update pattern")


@patterns_router.delete("/{pattern_id}", response_model=PatternResponse)
async def delete_pattern(
    pattern_id: str, pattern_manager: PatternManager = Depends(get_pattern_manager)
):
    """Delete a pattern by ID
    """
    try:
        if pattern_manager.delete_pattern(pattern_id):
            logger.info("pattern_deleted_via_api", pattern_id=pattern_id)

            return PatternResponse(
                success=True, message=f"Pattern '{pattern_id}' deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=404, detail=f"Pattern '{pattern_id}' not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_pattern_failed", pattern_id=pattern_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete pattern")


# Bulk Operations


@patterns_router.post("/bulk", response_model=Dict[str, Any])
async def bulk_add_patterns(
    request: Dict[str, Any],
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Add multiple patterns in bulk
    """
    try:
        patterns_data = request.get("patterns", [])
        pattern_set_name = request.get("pattern_set_name", "bulk")

        if not patterns_data:
            raise HTTPException(status_code=400, detail="No patterns provided")

        # Convert to Pattern objects
        patterns = [Pattern(**pattern_data) for pattern_data in patterns_data]

        results = pattern_manager.bulk_add_patterns(patterns, pattern_set_name)

        logger.info(
            "bulk_add_patterns_via_api",
            added=len(results["added"]),
            failed=len(results["failed"]),
        )

        return {
            "operation": "bulk_add",
            "pattern_set": pattern_set_name,
            "results": results,
            "summary": {
                "total_submitted": len(patterns_data),
                "added": len(results["added"]),
                "failed": len(results["failed"]),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("bulk_add_patterns_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to bulk add patterns")


@patterns_router.put("/bulk", response_model=Dict[str, Any])
async def bulk_update_patterns(
    request: Dict[str, Any],
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Update multiple patterns in bulk
    """
    try:
        patterns_data = request.get("patterns", [])

        if not patterns_data:
            raise HTTPException(status_code=400, detail="No patterns provided")

        # Convert to Pattern objects
        patterns = [Pattern(**pattern_data) for pattern_data in patterns_data]

        results = pattern_manager.bulk_update_patterns(patterns)

        logger.info(
            "bulk_update_patterns_via_api",
            updated=len(results["updated"]),
            failed=len(results["failed"]),
        )

        return {
            "operation": "bulk_update",
            "results": results,
            "summary": {
                "total_submitted": len(patterns_data),
                "updated": len(results["updated"]),
                "failed": len(results["failed"]),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("bulk_update_patterns_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to bulk update patterns")


@patterns_router.delete("/bulk", response_model=Dict[str, Any])
async def bulk_delete_patterns(
    request: Dict[str, Any],
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Delete multiple patterns in bulk
    """
    try:
        pattern_ids = request.get("pattern_ids", [])

        if not pattern_ids:
            raise HTTPException(status_code=400, detail="No pattern IDs provided")

        results = pattern_manager.bulk_delete_patterns(pattern_ids)

        logger.info(
            "bulk_delete_patterns_via_api",
            deleted=len(results["deleted"]),
            not_found=len(results["not_found"]),
        )

        return {
            "operation": "bulk_delete",
            "results": results,
            "summary": {
                "total_submitted": len(pattern_ids),
                "deleted": len(results["deleted"]),
                "not_found": len(results["not_found"]),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("bulk_delete_patterns_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to bulk delete patterns")


# Pattern State Management


@patterns_router.post("/{pattern_id}/enable", response_model=PatternResponse)
async def enable_pattern(
    pattern_id: str, pattern_manager: PatternManager = Depends(get_pattern_manager)
):
    """Enable a pattern
    """
    try:
        if pattern_manager.enable_pattern(pattern_id):
            return PatternResponse(
                success=True, message=f"Pattern '{pattern_id}' enabled successfully"
            )
        else:
            raise HTTPException(
                status_code=404, detail=f"Pattern '{pattern_id}' not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("enable_pattern_failed", pattern_id=pattern_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enable pattern")


@patterns_router.post("/{pattern_id}/disable", response_model=PatternResponse)
async def disable_pattern(
    pattern_id: str, pattern_manager: PatternManager = Depends(get_pattern_manager)
):
    """Disable a pattern
    """
    try:
        if pattern_manager.disable_pattern(pattern_id):
            return PatternResponse(
                success=True, message=f"Pattern '{pattern_id}' disabled successfully"
            )
        else:
            raise HTTPException(
                status_code=404, detail=f"Pattern '{pattern_id}' not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("disable_pattern_failed", pattern_id=pattern_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to disable pattern")


# File Upload Operations


@patterns_router.post("/upload", response_model=Dict[str, Any])
async def upload_pattern_file(
    file: UploadFile = File(...),
    pattern_set_name: str = None,
    merge_with_existing: bool = True,
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Upload a pattern file (JSON or YAML)

    - **file**: Pattern file (JSON or YAML format)
    - **pattern_set_name**: Name for the pattern set (defaults to filename or file's name field)
    - **merge_with_existing**: Whether to merge with existing patterns or replace
    """
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in [".json", ".yaml", ".yml"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_extension}. Supported: .json, .yaml, .yml",
            )

        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        try:
            content_str = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

        # Parse content based on file type
        try:
            if file_extension == ".json":
                data = json.loads(content_str)
            else:  # .yaml or .yml
                data = yaml.safe_load(content_str)
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid file format: {str(e)}"
            )

        # Validate and create pattern set
        try:
            pattern_set = PatternSet(**data)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid pattern set format: {str(e)}"
            )

        # Use provided name or fall back to file name or pattern set name
        final_name = pattern_set_name or pattern_set.name or Path(file.filename).stem
        pattern_set.name = final_name

        # Validate all patterns
        validation_errors = []
        for pattern in pattern_set.patterns:
            errors = pattern_manager.validate_pattern(pattern)
            if errors:
                validation_errors.extend(
                    [f"Pattern {pattern.id}: {error}" for error in errors]
                )

        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Pattern validation failed",
                    "errors": validation_errors[:10],  # Limit to first 10 errors
                },
            )

        # Check for conflicts if not merging
        conflicts = []
        if not merge_with_existing:
            for pattern in pattern_set.patterns:
                if pattern.id in pattern_manager.patterns:
                    conflicts.append(pattern.id)

        if conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Pattern conflicts found (use merge_with_existing=true to merge)",
                    "conflicts": conflicts[:10],  # Limit to first 10 conflicts
                },
            )

        # Add pattern set
        if merge_with_existing and final_name in pattern_manager.pattern_sets:
            # Merge with existing set
            existing_set = pattern_manager.pattern_sets[final_name]

            # Add new patterns, skip duplicates
            added_patterns = []
            skipped_patterns = []

            for pattern in pattern_set.patterns:
                if pattern.id not in pattern_manager.patterns:
                    existing_set.patterns.append(pattern)
                    added_patterns.append(pattern.id)
                else:
                    skipped_patterns.append(pattern.id)

            pattern_manager._rebuild_pattern_index()

            result = {
                "operation": "upload_merge",
                "filename": file.filename,
                "pattern_set": final_name,
                "total_in_file": len(pattern_set.patterns),
                "added": len(added_patterns),
                "skipped": len(skipped_patterns),
                "added_patterns": added_patterns,
                "skipped_patterns": skipped_patterns,
            }
        else:
            # Add as new pattern set or replace existing
            pattern_manager.add_pattern_set(pattern_set)

            result = {
                "operation": "upload_add",
                "filename": file.filename,
                "pattern_set": final_name,
                "total_patterns": len(pattern_set.patterns),
                "enabled_patterns": len(pattern_set.get_enabled_patterns()),
            }

        logger.info(
            "pattern_file_uploaded",
            filename=file.filename,
            pattern_set=final_name,
            patterns=len(pattern_set.patterns),
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_pattern_file_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to upload pattern file")


@patterns_router.post("/upload/bulk", response_model=Dict[str, Any])
async def upload_multiple_pattern_files(
    files: List[UploadFile] = File(...),
    merge_with_existing: bool = True,
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Upload multiple pattern files at once

    - **files**: List of pattern files (JSON or YAML format)
    - **merge_with_existing**: Whether to merge with existing patterns
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        results = {
            "uploaded": [],
            "failed": [],
            "errors": [],
            "summary": {
                "total_files": len(files),
                "successful": 0,
                "failed": 0,
                "total_patterns": 0,
            },
        }

        for file in files:
            try:
                # Process each file individually
                file_content = await file.read()
                file.file.seek(0)  # Reset file pointer for potential retry

                # Use the single file upload logic
                upload_result = await upload_pattern_file(
                    file=file,
                    pattern_set_name=None,
                    merge_with_existing=merge_with_existing,
                    pattern_manager=pattern_manager,
                )

                results["uploaded"].append(
                    {"filename": file.filename, "result": upload_result}
                )
                results["summary"]["successful"] += 1
                results["summary"]["total_patterns"] += upload_result.get(
                    "total_patterns", 0
                )

            except HTTPException as e:
                results["failed"].append(file.filename)
                results["errors"].append(f"{file.filename}: {e.detail}")
                results["summary"]["failed"] += 1
            except Exception as e:
                results["failed"].append(file.filename)
                results["errors"].append(f"{file.filename}: {str(e)}")
                results["summary"]["failed"] += 1

        logger.info(
            "bulk_pattern_upload_completed",
            total=len(files),
            successful=results["summary"]["successful"],
            failed=results["summary"]["failed"],
        )

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error("bulk_upload_pattern_files_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to upload pattern files")


@patterns_router.post("/download/{set_name}")
async def download_pattern_set(
    set_name: str,
    format: str = "yaml",
    pattern_manager: PatternManager = Depends(get_pattern_manager),
):
    """Download a pattern set as a file

    - **set_name**: Name of the pattern set to download
    - **format**: File format (json or yaml)
    """
    try:
        if set_name not in pattern_manager.pattern_sets:
            raise HTTPException(
                status_code=404, detail=f"Pattern set '{set_name}' not found"
            )

        pattern_set = pattern_manager.pattern_sets[set_name]

        if format.lower() == "json":
            content = json.dumps(pattern_set.model_dump(), indent=2)
            media_type = "application/json"
            filename = f"{set_name}.json"
        else:  # yaml
            content = yaml.dump(pattern_set.model_dump(), default_flow_style=False)
            media_type = "application/x-yaml"
            filename = f"{set_name}.yaml"

        from fastapi.responses import Response

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("download_pattern_set_failed", set_name=set_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to download pattern set")
