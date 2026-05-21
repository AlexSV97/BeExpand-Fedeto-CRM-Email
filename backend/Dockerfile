# ── Stage 1: Builder ──
FROM python:3.12-slim AS builder

WORKDIR /app

# Dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python (global, no --user, para evitar problemas de
# permisos al ejecutar con usuario no-root en la etapa runtime)
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.12-slim

WORKDIR /app

# Crear usuario no-root
RUN groupadd -r beexpand && useradd -r -g beexpand -d /app -s /bin/false beexpand

# Copiar site-packages del builder (instalación global → /usr/local/)
COPY --from=builder /usr/local /usr/local

# Copiar código
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

# Entrypoint para esperar a PostgreSQL (si se usa)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Puerto
EXPOSE 8000

USER beexpand

ENTRYPOINT ["/docker-entrypoint.sh"]
# Por defecto: lanzar API
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
