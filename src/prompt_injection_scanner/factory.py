"""
Factory pattern for scanner creation - abstracts configuration complexity
Follows KISS and Builder pattern principles
"""

from typing import Optional, Dict, Any
from .core.scanner import Scanner
from .stages.heuristic import HeuristicStage
from .stages.vector import VectorStage
from .stages.guardian import GuardianStage
from .patterns import PatternManager


class ScannerBuilder:
    """
    Builder pattern for scanner configuration
    KISS: Simple fluent interface, YAGNI: only what we need
    """
    
    def __init__(self):
        self._vector_db = None
        self._guardian_model = "openai:gpt-4"
        self._pattern_manager = None
        self._config = {}
    
    def with_vector_db(self, vector_db_client):
        """Configure vector database - dependency injection"""
        self._vector_db = vector_db_client
        return self
    
    def with_guardian_model(self, model_name: str):
        """Configure guardian AI model"""
        self._guardian_model = model_name
        return self
    
    def with_pattern_manager(self, pattern_manager: PatternManager):
        """Configure pattern manager"""
        self._pattern_manager = pattern_manager
        return self
    
    def with_config(self, **config):
        """Additional configuration options"""
        self._config.update(config)
        return self
    
    def build(self) -> Scanner:
        """Build the scanner with configured components"""
        pattern_manager = self._pattern_manager or PatternManager()
        
        return Scanner(
            heuristic_stage=HeuristicStage(pattern_manager),
            vector_stage=VectorStage(self._vector_db),
            guardian_stage=GuardianStage(self._guardian_model)
        )


class ScannerFactory:
    """
    Factory for common scanner configurations
    Abstracts away complex setup for common use cases
    """
    
    @staticmethod
    def create_basic() -> Scanner:
        """Basic scanner without vector DB - YAGNI for simple cases"""
        return ScannerBuilder().build()
    
    @staticmethod
    def create_with_vector_db(vector_db_client) -> Scanner:
        """Scanner with vector similarity enabled"""
        return (ScannerBuilder()
                .with_vector_db(vector_db_client)
                .build())
    
    @staticmethod
    def create_full_featured(vector_db_client, guardian_model: str = "openai:gpt-4") -> Scanner:
        """Full-featured scanner with all stages optimized"""
        return (ScannerBuilder()
                .with_vector_db(vector_db_client)
                .with_guardian_model(guardian_model)
                .build())
    
    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> Scanner:
        """Create scanner from configuration dict - for dependency injection"""
        builder = ScannerBuilder()
        
        if "vector_db" in config:
            builder.with_vector_db(config["vector_db"])
        
        if "guardian_model" in config:
            builder.with_guardian_model(config["guardian_model"])
        
        return builder.build()


# Simple module-level functions for common usage - KISS principle
def create_scanner(vector_db_client=None, guardian_model: str = "openai:gpt-4") -> Scanner:
    """Simple function for most common use case"""
    if vector_db_client:
        return ScannerFactory.create_with_vector_db(vector_db_client)
    return ScannerFactory.create_basic()