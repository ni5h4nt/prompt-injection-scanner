"""
Clean public API - hides complexity, exposes simple interface
KISS principle: Easy to use, hard to misuse
"""

from .api.models import RiskLevel, ScanRequest, ScanResponse
from .core.scanner import ScanContext, Scanner, ScanResult
from .factory import ScannerBuilder, ScannerFactory, create_scanner

# Simple public interface - YAGNI principle
__all__ = [
    # Main scanner creation
    "create_scanner",
    "ScannerFactory",
    "ScannerBuilder",
    # Core types users need
    "Scanner",
    "ScanResult",
    "ScanRequest",
    "ScanResponse",
    "RiskLevel",
]

# Version info
__version__ = "0.1.0"
