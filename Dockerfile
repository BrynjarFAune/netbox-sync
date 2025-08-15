FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source and install
COPY src/ ./src/
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Create data directory and non-root user
RUN mkdir -p /app/data && \
    groupadd -r appuser && \
    useradd -r -g appuser -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

# Default command
CMD ["netbox-sync", "serve"]

# Labels for metadata
LABEL maintainer="your.email@example.com"
LABEL description="NetBox Infrastructure Sync Tool"
LABEL version="0.1.0"