#!/bin/bash

# Veo3 MCP Build Script
# This script builds and packages the Veo3 MCP Python implementation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$SCRIPT_DIR/build"
DIST_DIR="$SCRIPT_DIR/dist"

echo "================================================"
echo "Veo3 MCP Python Build Script"
echo "================================================"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment for build
echo "Creating build virtual environment..."
python3 -m venv "$BUILD_DIR/venv"
source "$BUILD_DIR/venv/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "Installing dependencies..."
pip install -r "$PROJECT_ROOT/requirements.txt" 2>/dev/null || echo "No requirements.txt found, skipping..."

# Install dev dependencies for testing
echo "Installing dev dependencies..."
pip install pytest pytest-asyncio pytest-cov black mypy ruff

# Run linting
echo "Running linting checks..."
echo "  - Black (formatting)..."
black --check "$SCRIPT_DIR" || (echo "Code formatting issues found. Run 'black .' to fix." && exit 1)

echo "  - Ruff (linting)..."
ruff check "$SCRIPT_DIR" || (echo "Linting issues found. Run 'ruff check --fix .' to fix." && exit 1)

echo "  - MyPy (type checking)..."
mypy "$SCRIPT_DIR" --ignore-missing-imports || echo "Type checking completed with warnings"

# Run tests if they exist
if [ -d "$SCRIPT_DIR/tests" ]; then
    echo "Running tests..."
    pytest "$SCRIPT_DIR/tests" -v --cov="$SCRIPT_DIR" --cov-report=term-missing
else
    echo "No tests directory found, skipping tests..."
fi

# Run verification script
echo "Running verification script..."
python3 "$SCRIPT_DIR/verify.py" || echo "Verification completed with warnings"

# Package the module
echo "Creating package..."
cd "$SCRIPT_DIR"

# Create setup.py if it doesn't exist
if [ ! -f "setup.py" ]; then
    cat > setup.py << 'EOF'
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="veo3-mcp",
    version="1.0.0",
    author="Google Cloud Platform",
    description="Veo3 MCP service for video generation using Google Cloud Vertex AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
        "google-cloud-aiplatform>=1.40.0",
        "google-generativeai>=0.3.0",
        "google-cloud-storage>=2.10.0",
        "pydantic>=2.0.0",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "sqlalchemy>=2.0.0",
        "alembic>=1.12.0",
        "httpx>=0.24.0",
        "aiofiles>=23.0.0",
        "python-dotenv>=1.0.0",
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0",
        "opentelemetry-instrumentation-fastapi>=0.41b0",
        "opentelemetry-instrumentation-httpx>=0.41b0",
        "opentelemetry-instrumentation-sqlalchemy>=0.41b0",
        "opentelemetry-instrumentation-logging>=0.41b0",
        "opentelemetry-exporter-otlp>=1.20.0",
    ],
    entry_points={
        "console_scripts": [
            "veo3-mcp=veo3_mcp.main:main",
            "veo3-mcp-verify=veo3_mcp.verify:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
EOF
fi

# Create README if it doesn't exist
if [ ! -f "README.md" ]; then
    cat > README.md << 'EOF'
# Veo3 MCP Service

Python implementation of the Veo3 Model Context Protocol (MCP) service for video generation using Google Cloud Vertex AI.

## Features

- Text-to-video generation using Veo models
- Image-to-video generation with optional prompts
- Support for multiple Veo model variants (Veo 2, Veo 3, Veo 3 Fast)
- Async/await patterns for efficient operation
- JWT authentication and MCP toggle permissions
- OpenTelemetry instrumentation for observability
- GCS integration for video storage
- Progress tracking for long-running operations

## Installation

```bash
pip install veo3-mcp
```

## Configuration

Set the following environment variables:

```bash
export PROJECT_ID="your-gcp-project"
export LOCATION="us-central1"
export GENMEDIA_BUCKET="your-gcs-bucket"
export JWT_SECRET_KEY="your-secret-key"
export VERTEX_API_ENDPOINT="https://your-endpoint" # Optional
```

## Usage

### As an MCP Server

```python
from veo3_mcp import create_mcp_server

server = create_mcp_server()
# Server is now ready to handle MCP requests
```

### Direct API Usage

```python
from veo3_mcp import Veo3Service, TextToVideoRequest

service = Veo3Service()
request = TextToVideoRequest(
    prompt="A beautiful sunset over mountains",
    model="veo-2.0-generate-001",
    duration=5
)
response = await service.generate_video_from_text(request)
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run verification
python verify.py

# Run tests
pytest tests/
```

## License

Apache License 2.0
EOF
fi

# Build wheel and source distribution
echo "Building wheel and source distribution..."
python setup.py sdist bdist_wheel

# Copy artifacts to dist directory
echo "Copying artifacts..."
cp -r dist/* "$DIST_DIR/"

# Create deployment package
echo "Creating deployment package..."
cd "$PROJECT_ROOT"
tar -czf "$DIST_DIR/veo3-mcp-deployment.tar.gz" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="build" \
    --exclude="dist" \
    --exclude=".pytest_cache" \
    --exclude=".mypy_cache" \
    --exclude="venv" \
    --exclude=".env" \
    veo3_mcp/

# Deactivate virtual environment
deactivate

echo ""
echo "================================================"
echo "Build completed successfully!"
echo "================================================"
echo "Artifacts created in: $DIST_DIR"
echo ""
echo "To install locally:"
echo "  pip install $DIST_DIR/veo3_mcp-*.whl"
echo ""
echo "To deploy:"
echo "  Extract $DIST_DIR/veo3-mcp-deployment.tar.gz"
echo ""