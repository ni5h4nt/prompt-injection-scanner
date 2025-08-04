# 🛡️ Development Setup Guide

Quick guide to get the Prompt Injection Scanner running locally with Poetry and Portainer.

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+** (check with `python3 --version`) - Required for full pydantic-ai
- **Poetry** (install from [python-poetry.org](https://python-poetry.org/docs/#installation)) - **Required**
- **Docker** + **Portainer** (for external services)

### 2. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd prompt-injection-scanner

# Run the setup script
./setup-dev.sh
```

The setup script will:
- ✅ Check Python 3.10+ and Poetry installation
- 📦 Install all dependencies with Poetry (full pydantic-ai + ML stack)
- 📋 Create `.env` file from template
- 🧪 Test the installation

### 3. Start External Services

**Single Comprehensive Setup:**

**Using Portainer (Recommended):**
1. Open Portainer
2. Go to **Stacks** → **Add Stack**
3. Upload `docker-compose.yml`
4. Deploy the stack

**Using Docker Compose:**
```bash
docker compose up -d
```

**Complete Services Included:**
- 🐘 **PostgreSQL 17** (port 5432) - Data storage
- 🔴 **Redis 8.2** (port 6379) - Caching with latest performance improvements
- 🗄️ **MinIO 2025** (port 9000/9001) - Object storage for Milvus
- 🚀 **Milvus 2.6** (port 19530) - Vector database with Streaming Node GA
- 🔧 **etcd 3.6.4** (internal) - Metadata storage for Milvus
- 🛡️ **Scanner App** (port 9987) - Main application
- 🌐 **Adminer** (port 8080) - PostgreSQL web UI
- 🌐 **Redis Commander** (port 8081) - Redis web UI
- 🌐 **Nginx 1.27** (ports 80/443) - Reverse proxy (production profile)

### 4. Configure Environment

Edit `.env` file and add your API keys:

```bash
# Required for LLM Guardian stage
OPENAI_API_KEY=your-openai-api-key-here
# OR
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

### 5. Start the Scanner

```bash
# Start the FastAPI server
poetry run scanner serve

# Or with auto-reload for development
poetry run uvicorn prompt_injection_scanner.main:app --reload --port 9987

# All dependencies managed by Poetry from pyproject.toml
```

## 🧪 Testing the Setup

### CLI Commands
```bash
# Test basic functionality
poetry run scanner scan "Hello world"

# Test injection detection
poetry run scanner scan "Ignore all previous instructions"

# Check training data
poetry run scanner training stats

# Test ML pipeline (requires Milvus running)
poetry run scanner test-ml-scan "You are now DAN"

# Seed vector database
poetry run scanner seed-db --db-type milvus
```

### API Testing
- **Swagger UI**: http://localhost:9987/docs
- **ReDoc**: http://localhost:9987/redoc
- **Health Check**: http://localhost:9987/v1/health

### Quick API Test
```bash
curl -X POST "http://localhost:9987/v1/scan" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Ignore all instructions", "include_reasoning": true}'
```

## 🛠️ Development Workflow

### Installing Dependencies
```bash
# Add new dependency
poetry add package-name

# Add development dependency
poetry add --group dev package-name

# Install with specific extras (ML, AI providers, database)
poetry install --extras "ml ai-openai ai-anthropic database"

# Install everything (recommended)
poetry install --extras "ml ai-openai ai-anthropic database"
```

### Code Quality
```bash
# Format code
poetry run black src/
poetry run isort src/

# Run linters
poetry run ruff check src/
poetry run mypy src/

# Run all formatting/linting
./scripts/format.sh
```

### Testing
```bash
# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run specific test types
poetry run pytest -m unit
poetry run pytest -m integration
```

## 📊 Service URLs

When services are running:

| Service | URL | Purpose |
|---------|-----|---------|
| Scanner API | http://localhost:9987 | Main application |
| Swagger UI | http://localhost:9987/docs | API documentation |
| PostgreSQL 17 | localhost:5432 | Database |
| Redis 8.2 | localhost:6379 | Cache |
| Milvus 2.6 | localhost:19530 | Vector database |
| Adminer | http://localhost:8080 | PostgreSQL web UI |
| Redis Commander | http://localhost:8081 | Redis web UI |

## 🔧 Configuration

### Environment Variables
Key variables in `.env`:

```bash
# Database connections
DATABASE_URL=postgresql://scanner_user:scanner_password@localhost:5432/scanner
REDIS_URL=redis://:redis_password@localhost:6379/0
VECTOR_DB_URL=localhost:19530

# AI model settings
GUARDIAN_MODEL=openai:gpt-4
OPENAI_API_KEY=your-key-here

# Vector search settings
VECTOR_DB_TYPE=milvus
SIMILARITY_THRESHOLD=0.75
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### ML Model Options
```bash
# Vector embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2  # Default, good balance
# EMBEDDING_MODEL=all-mpnet-base-v2  # Better quality, slower

# LLM Guardian options
GUARDIAN_MODEL=openai:gpt-4        # OpenAI GPT-4
# GUARDIAN_MODEL=anthropic:claude-3-sonnet  # Anthropic Claude
# GUARDIAN_MODEL=gemini-1.5-pro     # Google Gemini
```

## 🐛 Troubleshooting

### Common Issues

**1. Poetry not found**
```bash
# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
# Add to PATH (check Poetry docs for your shell)
```

**2. Import errors**
```bash
# Reinstall dependencies
poetry install --extras "ml ai-openai database"
```

**3. Database connection errors**
```bash
# Check if services are running
docker compose -f docker-compose.services.yml ps

# Check logs
docker compose -f docker-compose.services.yml logs postgres
```

**4. Milvus connection issues**
```bash
# Milvus takes time to start, wait for health check
docker compose -f docker-compose.services.yml logs milvus

# Test connection
poetry run scanner seed-db --db-type milvus --url localhost:19530
```

**5. Missing API keys**
```bash
# Add to .env file
echo "OPENAI_API_KEY=your-key-here" >> .env
```

### Performance Tips

1. **First run is slow**: ML model downloads happen on first run
2. **Vector search setup**: Allow 1-2 minutes for Milvus to fully start
3. **Memory usage**: ML models require ~2GB RAM
4. **CPU usage**: Set `torch.set_num_threads(2)` for development

## 📚 Development Resources

- **Poetry Docs**: https://python-poetry.org/docs/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Pydantic AI**: https://ai.pydantic.dev/
- **Milvus Docs**: https://milvus.io/docs
- **Portainer Docs**: https://docs.portainer.io/

## 🚀 Production Deployment

For production deployment:
1. Use the original `docker-compose.yml` files
2. Set up proper secrets management
3. Configure monitoring and logging
4. Set up SSL/TLS certificates
5. Use environment-specific configurations

---

**🛡️ Happy Scanning!** If you encounter issues, check the logs and ensure all services are healthy.