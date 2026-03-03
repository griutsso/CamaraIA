# ═══════════════════════════════════════════════════════════════
#  IA-CAM-SERVICE — Dockerfile Multi-Stage
#  Soporta: amd64 (desarrollo) + arm64 (Raspberry Pi / Jetson)
# ═══════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──
FROM python:3.10-slim AS builder

WORKDIR /build

# Dependencias del sistema para OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime ──
FROM python:3.10-slim AS runtime

# Metadatos
LABEL maintainer="IA-CAM-SERVICE Team"
LABEL version="0.1.0"
LABEL description="Sistema de Visión Artificial Offline para Automóviles"

WORKDIR /app

# Dependencias runtime mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash iacam

# Copiar dependencias Python del builder
COPY --from=builder /install /usr/local

# Copiar código fuente
COPY . .

# Crear directorios de datos
RUN mkdir -p data/captures logs models \
    && chown -R iacam:iacam /app

# Usuario no-root
USER iacam

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Exponer puerto para API futura
EXPOSE 8080

# Punto de entrada
ENTRYPOINT ["python", "main.py"]
CMD ["--headless"]
