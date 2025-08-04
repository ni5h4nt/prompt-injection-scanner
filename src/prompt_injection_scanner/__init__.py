"""
Clean public API - hides complexity, exposes simple interface
KISS principle: Easy to use, hard to misuse
"""

from .factory import create_scanner, ScannerFactory, ScannerBuilder
from .core.scanner import Scanner, ScanResult, ScanContext
from .api.models import ScanRequest, ScanResponse, RiskLevel

# Simple public interface - YAGNI principle
__all__ = [
    # Main scanner creation
    'create_scanner',
    'ScannerFactory', 
    'ScannerBuilder',
    
    # Core types users need
    'Scanner',
    'ScanResult',
    'ScanRequest',
    'ScanResponse',
    'RiskLevel',
]

# Version info
__version__ = "0.1.0"