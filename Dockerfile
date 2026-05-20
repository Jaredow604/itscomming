# Multi-stage Dockerfile para Producción
# Stage 1: Build
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar dependencias del sistema necesarias para compilar psycopg2, scipy, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Production Run
FROM python:3.11-slim

WORKDIR /app

# Librerías de sistema en el contenedor final
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar wheels y requirements
COPY --from=builder /app/wheels /wheels
COPY requirements.txt .

# Instalar los wheels
RUN pip install --no-cache /wheels/*

# Copiar código fuente
COPY . .

# Recolectar estáticos
RUN python manage.py collectstatic --noinput || true

# Exponer el puerto
EXPOSE 8000

# Comando por defecto para web
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "core.wsgi:application"]
