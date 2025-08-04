#!/bin/bash
# Code formatting and linting script for the prompt injection scanner

set -e

echo "🔧 Starting code formatting and linting..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Using virtual environment"
    source venv/bin/activate
fi

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Please run from project root."
    exit 1
fi

echo "📁 Working directory: $(pwd)"

# Install linting dependencies if not already installed
echo "📦 Installing/updating linting tools..."
pip install -q black isort mypy ruff bandit safety

# Format imports with isort
echo "🔄 Sorting imports with isort..."
isort src/ --profile black --line-length 88 --multi-line 3 --check-only --diff || {
    echo "📝 Fixing import order..."
    isort src/ --profile black --line-length 88 --multi-line 3
}

# Format code with black
echo "🖤 Formatting code with black..."
black src/ --line-length 88 --check --diff || {
    echo "📝 Applying black formatting..."
    black src/ --line-length 88
}

# Type checking with mypy
echo "🔍 Type checking with mypy..."
mypy src/ --ignore-missing-imports --no-strict-optional --allow-untyped-calls || {
    echo "⚠️  Type checking found issues (see above)"
}

# Linting with ruff
echo "🚀 Linting with ruff..."
ruff check src/ --fix || {
    echo "⚠️  Ruff found issues (see above)"
}

# Security linting with bandit
echo "🔒 Security scanning with bandit..."
bandit -r src/ -f json -o security-scan-results.json -ll || {
    echo "⚠️  Security issues found (check security-scan-results.json)"
}

# Check for known security vulnerabilities in dependencies
echo "🛡️  Checking dependencies for security vulnerabilities..."
safety check --json || {
    echo "⚠️  Dependency security issues found"
}

echo "✅ Code formatting and linting complete!"
echo ""
echo "📋 Summary:"
echo "   - Import sorting: isort (PEP 8 compatible)"
echo "   - Code formatting: black (88 char line length)"
echo "   - Type checking: mypy (with relaxed settings)"
echo "   - Linting: ruff (fast Python linter)"
echo "   - Security: bandit + safety check"
echo ""
echo "🔧 To fix issues automatically, run:"
echo "   black src/"
echo "   isort src/ --profile black"
echo "   ruff check src/ --fix"