"""
API v1 models - versioned data structures
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class RiskLevel(str, Enum):
    """Risk level enumeration - v1"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class ScanRequest(BaseModel):
    """v1 Scan request model"""
    prompt: str = Field(..., min_length=1, max_length=10000, description="Text to scan for injection")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    request_id: Optional[str] = Field(None, description="Optional request tracking ID")
    
    # v1 specific fields
    include_reasoning: bool = Field(default=False, description="Include detailed reasoning in response")
    
    @validator('prompt')
    def validate_prompt(cls, v):
        """Simple validation"""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()


class StageResult(BaseModel):
    """Individual stage result - v1"""
    stage_name: str = Field(..., description="Name of the analysis stage")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score from this stage")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Stage confidence")
    flags: List[str] = Field(default_factory=list, description="Flags raised by this stage")
    processing_time_ms: Optional[int] = Field(None, description="Time taken by this stage")


class ScanResponse(BaseModel):
    """v1 Scan response model"""
    # Core results
    risk_score: int = Field(..., ge=0, le=100, description="Overall risk score 0-100")
    risk_level: RiskLevel = Field(..., description="Risk level category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall analysis confidence")
    
    # Detection details
    flags: List[str] = Field(default_factory=list, description="All detected threat flags")
    threat_types: Optional[List[str]] = Field(default_factory=list, description="Detected threat categories")
    
    # Stage breakdown
    stage_results: List[StageResult] = Field(default_factory=list, description="Individual stage results")
    stage_scores: Dict[str, int] = Field(default_factory=dict, description="Legacy stage scores")
    
    # Metadata
    processing_time_ms: Optional[int] = Field(None, description="Total processing time")
    request_id: str = Field(..., description="Request tracking ID")
    api_version: str = Field(default="v1", description="API version used")
    
    # Optional fields
    reasoning: Optional[str] = Field(None, description="Detailed reasoning (if requested)")
    recommendations: Optional[List[str]] = Field(default_factory=list, description="Security recommendations")
    
    @validator('risk_level', pre=True, always=True)
    def compute_risk_level(cls, v, values):
        """Compute risk level from score"""
        if 'risk_score' not in values:
            return v
        
        score = values['risk_score']
        if score >= 85:
            return RiskLevel.CRITICAL
        elif score >= 65:
            return RiskLevel.HIGH
        elif score >= 35:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


class ErrorResponse(BaseModel):
    """v1 Error response model"""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    error_type: str = Field(default="validation_error", description="Error category")
    request_id: Optional[str] = Field(None, description="Request ID if available")
    api_version: str = Field(default="v1", description="API version")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """v1 Health check response"""
    status: str = Field(..., description="Service status")
    service: str = Field(default="prompt-injection-scanner", description="Service name")
    version: str = Field(..., description="Service version")
    api_version: str = Field(default="v1", description="API version")
    timestamp: str = Field(..., description="Response timestamp")
    components: Optional[Dict[str, str]] = Field(None, description="Component health status")


class BatchScanRequest(BaseModel):
    """v1 Batch scan request"""
    prompts: List[str] = Field(..., min_items=1, max_items=100, description="Prompts to scan")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Shared context")
    include_reasoning: bool = Field(default=False, description="Include reasoning for all scans")
    request_id: Optional[str] = Field(None, description="Batch request ID")


class BatchScanResponse(BaseModel):
    """v1 Batch scan response"""
    results: List[ScanResponse] = Field(..., description="Individual scan results")
    batch_id: str = Field(..., description="Batch processing ID")
    total_processed: int = Field(..., description="Number of prompts processed")
    processing_time_ms: int = Field(..., description="Total batch processing time")
    api_version: str = Field(default="v1", description="API version used")