"""API versioning utilities and configuration
Clean versioning strategy following best practices
"""

from enum import Enum
from typing import Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel


class APIVersion(str, Enum):
    """Supported API versions"""

    V1 = "v1"
    # Future versions would be added here
    # V2 = "v2"


class VersionConfig(BaseModel):
    """Version configuration"""

    current: APIVersion = APIVersion.V1
    supported: list[APIVersion] = [APIVersion.V1]
    deprecated: list[APIVersion] = []
    sunset_dates: dict[str, str] = {}  # Version -> sunset date


def get_version_from_path(path: str) -> Optional[APIVersion]:
    """Extract API version from request path"""
    parts = path.strip("/").split("/")
    if len(parts) > 0 and parts[0].startswith("v"):
        try:
            return APIVersion(parts[0])
        except ValueError:
            return None
    return None


def get_version_from_header(request: Request) -> Optional[APIVersion]:
    """Extract API version from Accept header"""
    accept_header = request.headers.get("accept", "")

    # Support application/vnd.scanner.v1+json format
    if "application/vnd.scanner." in accept_header:
        try:
            version_part = accept_header.split("application/vnd.scanner.")[1].split(
                "+"
            )[0]
            return APIVersion(version_part)
        except (IndexError, ValueError):
            return None

    # Support custom header
    version_header = request.headers.get("api-version")
    if version_header:
        try:
            return APIVersion(version_header)
        except ValueError:
            return None

    return None


def determine_api_version(request: Request) -> APIVersion:
    """Determine API version from request
    Priority: Path > Accept Header > API-Version Header > Default
    """
    # Try path first (e.g., /v1/scan)
    version = get_version_from_path(request.url.path)
    if version:
        return version

    # Try headers
    version = get_version_from_header(request)
    if version:
        return version

    # Default to current version
    return APIVersion.V1


def validate_api_version(version: APIVersion, config: VersionConfig = None) -> None:
    """Validate that the requested API version is supported"""
    if config is None:
        config = VersionConfig()

    if version not in config.supported:
        if version in config.deprecated:
            sunset_date = config.sunset_dates.get(version.value)
            message = f"API version {version.value} is deprecated"
            if sunset_date:
                message += f" and will be sunset on {sunset_date}"

            # For deprecated versions, we could add a warning header
            # but still allow the request
            pass
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported API version: {version.value}. "
                f"Supported versions: {[v.value for v in config.supported]}",
            )


class VersionInfo(BaseModel):
    """Version information response"""

    current_version: str
    supported_versions: list[str]
    deprecated_versions: list[str]
    sunset_dates: dict[str, str]
