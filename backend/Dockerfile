FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Tesseract (eng+spa), OCRmyPDF, fuentes libres Noto y Calibre (ebook-convert, para el AZW3 de Kindle)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa \
        ocrmypdf ghostscript \
        calibre \
        fonts-noto-core fonts-noto-mono fonts-liberation \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios con el mismo UID/GID que el dueño de ./data en el host
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -g "${APP_GID}" app && useradd -m -u "${APP_UID}" -g app -d /home/app app

WORKDIR /app

# Dependencias primero (capa en caché mientras no cambie pyproject.toml)
COPY pyproject.toml ./
RUN pip install --no-cache-dir $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

ENV FONTS_DIRS=/app/fonts:/usr/share/fonts/truetype/noto \
    HOME=/home/app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Desarrollo (compose.dev.yml, `target: dev`): las mismas dependencias más las de [dev] (pytest, ruff), sin
# instalar el paquete (el código se importa desde /app, montado en dev). Sirve también para tests y lint.
FROM base AS dev
RUN pip install --no-cache-dir $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['optional-dependencies']['dev']))") \
    && chown app:app /app
COPY --chown=app:app . .
USER app

# Producción (stage final: lo que construye `docker compose up --build` sin target)
FROM base
COPY --chown=app:app . .
USER app
