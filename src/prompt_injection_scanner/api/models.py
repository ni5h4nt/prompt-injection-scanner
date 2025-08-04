"""
Clean API models with validation - abstracts serialization complexity
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class RiskLevel(str, Enum):
    """Risk level enumeration - KISS principle"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class ScanRequest(BaseModel):
    """Request model with validation"""
    prompt: str = Field(..., min_length=1, max_length=10000, description="Text to scan for injection")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    request_id: Optional[str] = Field(None, description="Optional request tracking ID")
    
    @validator('prompt')
    def validate_prompt(cls, v):
        """Simple validation - no complexity"""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()


class ScanResponse(BaseModel):
    """Response model with computed properties"""
    risk_score: int = Field(..., ge=0, le=100, description="Risk score 0-100")
    risk_level: RiskLevel = Field(..., description="Risk level category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Analysis confidence")
    flags: List[str] = Field(default_factory=list, description="Detected threat flags")
    stage_scores: Dict[str, int] = Field(default_factory=dict, description="Individual stage scores")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    request_id: str = Field(..., description="Request tracking ID")
    
    @validator('risk_level', pre=True, always=True)
    def compute_risk_level(cls, v, values):
        """Compute risk level from score - abstracted logic"""
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
    """Standard error response"""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    request_id: Optional[str] = Field(None, description="Request ID if available")