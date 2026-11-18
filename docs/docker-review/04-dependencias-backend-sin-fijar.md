# 04 · La imagen del backend instala dependencias sin versiones fijadas

- **Severidad:** Medio
- **Categoría:** Reproducibilidad
- **Estado:** resuelto · commit(s) `7083dd7`
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

Decisiones (opción recomendada):

- Un solo archivo, `backend/constraints.txt`, usado como restricciones (`-c`) en los dos `pip install` del
  Dockerfile: el de `[project.dependencies]` (stage `base`, heredado por el final) y el de `[dev]` (stage `dev`,
  que usan el stack dev y `backend-test`). Dos secciones: proyecto (63 paquetes) y `[dev]` (iniconfig, pluggy,
  Pygments, pytest 9.2.0, ruff 0.17.5). Con `-c` la producción no instala pytest/ruff y la lista de qué se instala
  sigue en `pyproject.toml` (sin duplicarla); el `pip freeze` de `api` debe coincidir con la primera sección.
- Versiones: las de la imagen de producción en marcha. El `pip freeze` del contenedor `api`, de
  `traductor-backend:latest`, de `:dev` (menos sus 5 de `[dev]`) y de `backend/.venv` eran idénticos (el `.venv`
  solo añade el propio paquete en modo editable): no hubo diferencias que elegir. P. ej. SQLAlchemy 2.1.9,
  FastAPI 0.163.1, Starlette 1.10.0, PyMuPDF 2.1.
- Sin herramientas nuevas (solo `pip freeze`); procedimiento de actualización en el `README.md` del repo («Versiones fijadas del
  backend»). Fuera de alcance: la imagen base `python:3.12-slim-bookworm` y los paquetes apt no se fijan.
- Tamaño (no se midió la reducción multi-stage, opcional): antes `traductor-backend` 2,45 GB y `:dev` 2,51 GB;
  después, igual (2,45 GB y 2,51 GB): mismas versiones, mismo contenido.
