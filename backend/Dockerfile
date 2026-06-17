# ── Stage 1: Builder ──
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (global, not --user)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create non-root user
RUN groupadd -r beexpand && useradd -r -g beexpand -d /app -s /bin/false beexpand

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy application code (filtered by .dockerignore)
COPY . .

# Entrypoint: waits for PostgreSQL if configured, otherwise passes through
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

USER beexpand

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]