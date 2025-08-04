"""Factory pattern for scanner creation - abstracts configuration complexity
Follows KISS and Builder pattern principles
"""

from typing import Any, Dict

import structlog

from .core.scanner import Scanner
from .patterns import PatternManager
from .stages.guardian import GuardianStage
from .stages.heuristic import HeuristicStage
from .stages.vector import VectorStage

logger = structlog.get_logger(__name__)


class ScannerBuilder:
    """Builder pattern for scanner configuration
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
            guardian_stage=GuardianStage(self._guardian_model),
        )


class ScannerFactory:
    """Factory for common scanner configurations
    Abstracts away complex setup for common use cases
    """

    @staticmethod
    def create_basic() -> Scanner:
        """Basic scanner without vector DB - YAGNI for simple cases"""
        return ScannerBuilder().build()

    @staticmethod
    def create_with_vector_db(vector_db_client) -> Scanner:
        """Scanner with vector similarity enabled"""
        return ScannerBuilder().with_vector_db(vector_db_client).build()

    @staticmethod
    def create_full_featured(
        vector_db_client, guardian_model: str = "openai:gpt-4"
    ) -> Scanner:
        """Full-featured scanner with all stages optimized"""
        return (
            ScannerBuilder()
            .with_vector_db(vector_db_client)
            .with_guardian_model(guardian_model)
            .build()
        )

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
def create_scanner(
    vector_db_client=None, guardian_model: str = "openai:gpt-4"
) -> Scanner:
    """Simple function for most common use case - auto-configures from environment"""
    from .config import get_config
    from .vector_db.factory import create_vector_db

    config = get_config()

    # Auto-create vector database if enabled and not provided
    if not vector_db_client and config.vector.enabled:
        try:
            vector_db_client = create_vector_db(
                db_type=config.vector.db_type,
                url=config.vector.url,
                api_key=config.vector.api_key,
            )
            logger.info(
                "auto_created_vector_db",
                db_type=config.vector.db_type,
                url=config.vector.url,
            )
        except Exception as e:
            logger.warning("vector_db_creation_failed", error=str(e))
            vector_db_client = None

    if vector_db_client:
        return ScannerFactory.create_with_vector_db(vector_db_client)
    return ScannerFactory.create_basic()
