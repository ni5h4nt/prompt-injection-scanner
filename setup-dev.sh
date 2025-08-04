#!/bin/bash
# Development setup script for Prompt Injection Scanner

set -e

echo "🛡️  Setting up Prompt Injection Scanner for local development"
echo "================================================="

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Please install Poetry first:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    echo "   Or visit: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    echo "❌ Python 3.10+ is required. You have Python $PYTHON_VERSION"
    echo "   Full pydantic-ai requires Python 3.10+"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"
echo "✅ Poetry is installed"

# Use Poetry pyproject.toml
if [ -f "pyproject-poetry.toml" ] && [ -f "pyproject.toml" ]; then
    echo "📝 Backing up original pyproject.toml and using Poetry version"
    mv pyproject.toml pyproject-hatchling.toml.bak
    mv pyproject-poetry.toml pyproject.toml
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies with Poetry..."
echo "   This may take a few minutes for ML dependencies..."

# Note: Poetry manages its own virtual environments
echo "   📦 Poetry will manage virtual environment automatically"

# Try Poetry first (multiple attempts to work around resolver bugs)
POETRY_SUCCESS=false

echo "   🔄 Attempting Poetry installation (full pydantic-ai)..."
for attempt in 1 2 3; do
    echo "   📦 Poetry attempt $attempt/3..."
    
    if timeout 300 poetry install --extras "ml ai-openai ai-anthropic database" --no-interaction 2>/dev/null; then
        echo "   ✅ Poetry installation successful on attempt $attempt"
        POETRY_SUCCESS=true
        break
    else
        echo "   ⚠️  Poetry attempt $attempt failed"
        if [ $attempt -lt 3 ]; then
            echo "   🔄 Clearing cache and retrying..."
            poetry cache clear pypi --all 2>/dev/null || true
            rm -f poetry.lock
        fi
    fi
done

if [ "$POETRY_SUCCESS" = false ]; then
    echo "   ❌ Poetry installation failed after 3 attempts"
    echo "   🔧 Please install Poetry manually and run again:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    echo "   Or visit: https://python-poetry.org/docs/#installation"
    exit 1
fi

echo ""
echo "🐳 External services setup:"
echo "   Single comprehensive Docker Compose file:"
echo "   - Import docker-compose.yml into Portainer"
echo "   - Or run: docker compose up -d"
echo "   "
echo "   Services included:"
echo "   - PostgreSQL 17 (port 5432) - Database"
echo "   - Redis 8.2 (port 6379) - Cache with performance improvements"
echo "   - Milvus 2.6 (port 19530) - Vector database with Streaming Node"
echo "   - MinIO 2025 (port 9000/9001) - Object storage"
echo "   - Adminer (port 8080) - Database UI"
echo "   - Redis Commander (port 8081) - Redis UI"
echo "   - Main Scanner App (port 9987) - API"
echo ""

# Setup environment file
if [ ! -f ".env" ]; then
    echo "📋 Creating .env file from template..."
    cp .env.local .env
    echo "   Please edit .env and add your API keys if needed"
else
    echo "📋 .env file already exists"
fi

# Make scripts executable
chmod +x scripts/*.sh

echo ""
echo "🔧 Available commands after setup:"
echo "   poetry run scanner --help          # CLI help"
echo "   poetry run scanner serve           # Start API server on port 9987"
echo "   poetry run scanner scan 'text'     # Quick scan"
echo "   poetry run uvicorn prompt_injection_scanner.main:app --reload --port 9987  # Dev server"
echo ""

echo "🧪 Testing the installation..."
echo "   🔍 Testing pydantic-ai (full version)..."
if poetry run python -c "import pydantic_ai; print('✅ Full pydantic-ai working')"; then
    echo "   🔍 Testing FastAPI..."
    if poetry run python -c "import fastapi; print('✅ FastAPI working')"; then
        echo "✅ Installation successful! Ready for full ML-powered scanning."
    else
        echo "❌ FastAPI test failed"
        exit 1
    fi
else
    echo "❌ pydantic-ai test failed"
    exit 1
fi

echo ""
echo "🚀 Next steps:"
echo "   1. Import docker-compose.yml into Portainer (or run: docker compose up -d)"
echo "   2. Edit .env file with your API keys (OpenAI, Anthropic, etc.)"
echo "   3. Run the scanner (see commands above)"
echo "   4. Visit: http://localhost:9987/docs for Swagger UI"
echo ""
echo "🔍 Quick test commands:"
echo "   poetry run scanner scan 'Hello world'"
echo "   poetry run scanner scan 'Ignore all previous instructions'"
echo "   poetry run scanner training stats"
echo ""

# Check if Docker is available for services
if command -v docker &> /dev/null; then
    echo "🐳 Docker detected. Single comprehensive setup:"
    echo ""
    echo "   📦 Complete application stack:"
    echo "   docker compose up -d"
    echo ""
    echo "   All services included: PostgreSQL 17, Redis 8.2, Milvus 2.6, MinIO 2025, Scanner App, Admin UIs"
    echo "   Perfect for Portainer deployment!"
else
    echo "🐳 Docker not detected. Please use Portainer with docker-compose.yml"
fi

echo ""
echo "✨ Setup complete! Happy scanning! 🛡️"