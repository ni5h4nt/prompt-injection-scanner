"""Pattern models for configurable detection rules
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    """Types of patterns supported"""

    REGEX = "regex"
    SUBSTRING = "substring"
    KEYWORD = "keyword"


class Severity(str, Enum):
    """Pattern severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Pattern(BaseModel):
    """Individual detection pattern"""

    id: str = Field(..., description="Unique pattern identifier")
    name: str = Field(..., description="Human-readable pattern name")
    description: str = Field(..., description="Pattern description")
    pattern: str = Field(..., description="The actual pattern (regex, substring, etc.)")
    pattern_type: PatternType = Field(
        default=PatternType.REGEX, description="Pattern type"
    )
    severity: Severity = Field(default=Severity.MEDIUM, description="Pattern severity")
    category: str = Field(..., description="Pattern category (e.g., 'system_override')")
    risk_score: int = Field(default=25, ge=0, le=100, description="Risk points to add")
    enabled: bool = Field(default=True, description="Whether pattern is active")
    case_sensitive: bool = Field(
        default=False, description="Case sensitivity for matching"
    )

    # Metadata
    created_by: Optional[str] = Field(None, description="Pattern creator")
    tags: List[str] = Field(default_factory=list, description="Pattern tags")
    references: List[str] = Field(
        default_factory=list, description="Reference URLs/docs"
    )
    examples: List[str] = Field(
        default_factory=list, description="Example matching strings"
    )


class PatternSet(BaseModel):
    """Collection of patterns with metadata"""

    name: str = Field(..., description="Pattern set name")
    version: str = Field(..., description="Pattern set version")
    description: str = Field(..., description="Pattern set description")
    author: Optional[str] = Field(None, description="Pattern set author")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")

    patterns: List[Pattern] = Field(
        default_factory=list, description="List of patterns"
    )

    def get_patterns_by_category(self, category: str) -> List[Pattern]:
        """Get patterns by category"""
        return [p for p in self.patterns if p.category == category and p.enabled]

    def get_patterns_by_severity(self, severity: Severity) -> List[Pattern]:
        """Get patterns by severity"""
        return [p for p in self.patterns if p.severity == severity and p.enabled]

    def get_enabled_patterns(self) -> List[Pattern]:
        """Get all enabled patterns"""
        return [p for p in self.patterns if p.enabled]


class PatternStats(BaseModel):
    """Statistics about loaded patterns"""

    total_patterns: int
    enabled_patterns: int
    patterns_by_category: Dict[str, int]
    patterns_by_severity: Dict[str, int]
    pattern_sets: List[str]
