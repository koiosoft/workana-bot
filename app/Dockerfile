# Usamos una base ligera pero robusta
FROM python:3.11-slim

# Evitar la generación de archivos .pyc y asegurar logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# 1. Instalar dependencias base del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Copiar e instalar requerimientos de Python primero (aprovechar cache de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. INSTALACIÓN CRÍTICA: Playwright 1.50.0 + Dependencias de Sistema
# El comando 'install-deps' asegura que Chromium tenga todas las libs necesarias
RUN playwright install chromium && \
    playwright install-deps chromium

# 4. Copiar el resto del código
COPY . .

# Comando de inicio
CMD ["python", "main.py"]