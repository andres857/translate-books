# Node solo aporta el runtime de la CLI oficial de Claude Code (modo suscripción)
FROM node:22-bookworm-slim AS node

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Tesseract (eng+spa), OCRmyPDF, fuentes libres Noto y Calibre (ebook-convert, para el AZW3 de Kindle)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa \
        ocrmypdf ghostscript \
        calibre \
        fonts-noto-core fonts-noto-mono fonts-liberation \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# CLI de Claude Code (versión fija; se autentica con CLAUDE_CODE_OAUTH_TOKEN de `claude setup-token`)
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
ARG CLAUDE_CODE_VERSION=2.1.322
RUN npm install -g --no-audit --no-fund "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force && claude --version

# Usuario sin privilegios con el mismo UID/GID que el dueño de ./data en el host
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -g "${APP_GID}" app && useradd -m -u "${APP_UID}" -g app -d /home/app app

WORKDIR /app

# Dependencias primero (capa en caché mientras no cambie pyproject.toml)
COPY pyproject.toml ./
RUN pip install --no-cache-dir $(python -c "import tomllib; print(' '.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")

COPY --chown=app:app . .

ENV FONTS_DIRS=/app/fonts:/usr/share/fonts/truetype/noto \
    HOME=/home/app CLAUDE_BIN=claude \
    DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
