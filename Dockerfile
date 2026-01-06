# Multi-stage build to minimize image size
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first
COPY pyproject.toml poetry.lock ./

# Install poetry
RUN pip install --no-cache-dir poetry

# Install dependencies to system Python (no venv in Docker)
# Only install main dependencies, exclude optional groups
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi && \
    rm -rf ~/.cache/pypoetry ~/.cache/pip /tmp/*

# Clean up build artifacts to reduce image size
RUN find /usr/local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local -type f -name "*.pyc" -delete 2>/dev/null || true

# Clean up build artifacts
RUN find /usr/local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local -type f -name "*.pyc" -delete 2>/dev/null || true

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy application code
COPY . .

# Expose port (Render sets PORT env var)
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health')" || exit 1

# Run with Uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
