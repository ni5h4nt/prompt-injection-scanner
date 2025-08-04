# Multi-stage Dockerfile for prompt injection scanner
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd --gid 1000 scanner && \
    useradd --uid 1000 --gid scanner --shell /bin/bash --create-home scanner

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency file
COPY pyproject.toml ./

# Install Poetry and dependencies
RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --extras "ml ai-openai ai-anthropic database" --without dev

# Development stage
FROM base as development

# Install development dependencies
RUN poetry install --extras "ml ai-openai ai-anthropic database"

# Copy source code
COPY --chown=scanner:scanner . .

USER scanner

# Default command for development
CMD ["python", "-m", "prompt_injection_scanner.cli", "serve", "--port", "9987"]

# Production stage
FROM base as production

# Copy source code
COPY --chown=scanner:scanner src/ ./src/
COPY --chown=scanner:scanner pyproject.toml ./

# Install the package
RUN poetry install --extras "ml ai-openai ai-anthropic database" --without dev

USER scanner

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9987/v1/health || exit 1

# Default production command
CMD ["python", "-c", "import uvicorn; from prompt_injection_scanner.main import app; uvicorn.run(app, host='0.0.0.0', port=9987)"]

# Expose port
EXPOSE 9987