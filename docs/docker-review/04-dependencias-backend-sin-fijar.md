# 04 · La imagen del backend instala dependencias sin versiones fijadas

- **Severidad:** Medio
- **Categoría:** Reproducibilidad
- **Estado:** abierto
- **Ubicación:** `backend/Dockerfile` (línea de `pip install … tomllib …`), `backend/pyproject.toml` (`dependencies` sin versiones o con `>=`)
- **Aceptación:** [04-dependencias-backend-sin-fijar.aceptacion.md](04-dependencias-backend-sin-fijar.aceptacion.md)

## Problema

El Dockerfile instala las dependencias leyendo `pyproject.toml`, casi todas sin versión (`fastapi`, `pymupdf>=1.24`,
`sqlalchemy>=2.0`…). Cada rebuild puede traer versiones nuevas (hoy SQLAlchemy 2.1.9, FastAPI 0.163) distintas a las
del `.venv` donde pasan los tests. Además la imagen pesa 2,45 GB (Calibre ≈ 400 MB).

## Cómo reproducirlo

Comparar `docker compose exec api pip freeze` con `backend/.venv/bin/pip freeze`: cualquier diferencia de versión es la deriva.

## Impacto

Un rebuild sin cambios de código puede romper la app (p. ej. una versión mayor de Starlette o PyMuPDF).

## Corrección propuesta

Generar un archivo de restricciones fijado (`backend/requirements.lock` o `constraints.txt`) con las versiones exactas que hoy pasan los tests (de `pip freeze` del `.venv`, solo las dependencias del proyecto y transitivas) e instalar con `pip install -r … ` / `-c …` en el Dockerfile. Documentar cómo actualizarlo. Opcional y anotado: medir si un build multi-stage reduce el tamaño sin quitar Calibre/Tesseract.

## Notas

No añadir herramientas nuevas (pip-tools, uv, poetry) sin preguntar: `pip freeze` basta. No cambiar versiones: fijar las que ya pasan los tests.
