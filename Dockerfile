# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Build arguments
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=0.1.0

# Labels
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.title="GitLab Discovery Agent" \
      org.opencontainers.image.description="Discovery agent for GitLab to GitHub migrations" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="Discovery Agent Team" \
      org.opencontainers.image.licenses="MIT"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
WORKDIR /build
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[all]"

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r discovery && useradd -r -g discovery -u 1000 discovery

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY discovery_agent/ ./discovery_agent/
COPY pyproject.toml ./

# Install the application
RUN pip install --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p /data/output /var/log/discovery-agent && \
    chown -R discovery:discovery /data /var/log/discovery-agent /app

# Switch to non-root user
USER discovery

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OUTPUT_DIR=/data/output \
    LOG_LEVEL=INFO \
    JSON_LOGGING=true \
    ENVIRONMENT=production

# Expose ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health/live || exit 1

# Default command
CMD ["python", "-m", "discovery_agent"]
