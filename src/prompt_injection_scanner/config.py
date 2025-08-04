"""
Configuration management with environment variables and defaults
Clean abstraction following KISS principle
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
from functools import lru_cache


class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="sqlite:///./scanner.db", description="Database URL")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL for caching")


class VectorConfig(BaseModel):
    """Vector database configuration"""
    enabled: bool = Field(default=False, description="Enable vector similarity search")
    db_type: str = Field(default="chromadb", description="Vector DB type: chromadb, pinecone, weaviate")
    url: Optional[str] = Field(default=None, description="Vector database URL")
    api_key: Optional[str] = Field(default=None, description="Vector database API key")


class GuardianConfig(BaseModel):
    """Guardian AI configuration"""
    model: str = Field(default="openai:gpt-4", description="Guardian AI model")
    api_key: Optional[str] = Field(default=None, description="AI provider API key")
    max_retries: int = Field(default=3, description="Max retries for AI requests")


class SecurityConfig(BaseModel):
    """Security and alerting configuration"""
    max_prompt_length: int = Field(default=10000, description="Maximum prompt length")
    rate_limit: int = Field(default=100, description="Requests per minute per IP")
    slack_webhook_url: Optional[str] = Field(default=None, description="Slack webhook for alerts")
    alert_min_confidence: float = Field(default=0.7, description="Minimum confidence for alerts")


class AppConfig(BaseModel):
    """Main application configuration"""
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Log level")
    
    # Component configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector: VectorConfig = Field(default_factory=VectorConfig)
    guardian: GuardianConfig = Field(default_factory=GuardianConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # Computed properties
    @property
    def vector_db_enabled(self) -> bool:
        return self.vector.enabled and self.vector.url is not None


def load_config_from_env() -> AppConfig:
    """Load configuration from environment variables"""
    
    # Server configuration
    server_config = {
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", "8000")),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }
    
    # Database configuration
    database_config = DatabaseConfig(
        url=os.getenv("DATABASE_URL", "sqlite:///./scanner.db"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    
    # Vector database configuration
    vector_config = VectorConfig(
        enabled=os.getenv("VECTOR_DB_ENABLED", "false").lower() == "true",
        db_type=os.getenv("VECTOR_DB_TYPE", "chromadb"),
        url=os.getenv("VECTOR_DB_URL"),
        api_key=os.getenv("VECTOR_DB_API_KEY")
    )
    
    # Guardian AI configuration
    guardian_config = GuardianConfig(
        model=os.getenv("GUARDIAN_MODEL", "openai:gpt-4"),
        api_key=os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        max_retries=int(os.getenv("GUARDIAN_MAX_RETRIES", "3"))
    )
    
    # Security configuration
    security_config = SecurityConfig(
        max_prompt_length=int(os.getenv("MAX_PROMPT_LENGTH", "10000")),
        rate_limit=int(os.getenv("API_RATE_LIMIT", "100")),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        alert_min_confidence=float(os.getenv("ALERT_MIN_CONFIDENCE", "0.7"))
    )
    
    return AppConfig(
        **server_config,
        database=database_config,
        vector=vector_config,
        guardian=guardian_config,
        security=security_config
    )


@lru_cache()
def get_config() -> AppConfig:
    """Get cached configuration - singleton pattern"""
    return load_config_from_env()


def get_example_env_file() -> str:
    """Generate example .env file content"""
    return """
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/scanner
REDIS_URL=redis://localhost:6379/0

# Vector Database Configuration
VECTOR_DB_ENABLED=true
VECTOR_DB_TYPE=chromadb
VECTOR_DB_URL=http://localhost:8001
VECTOR_DB_API_KEY=your-api-key

# Guardian AI Configuration
GUARDIAN_MODEL=openai:gpt-4
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
GUARDIAN_MAX_RETRIES=3

# Security Configuration
MAX_PROMPT_LENGTH=10000
API_RATE_LIMIT=100
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ALERT_MIN_CONFIDENCE=0.7
""".strip()


if __name__ == "__main__":
    # Print example configuration
    print("Example .env file:")
    print(get_example_env_file())
    
    print("\nCurrent configuration:")
    config = get_config()
    print(config.model_dump_json(indent=2))