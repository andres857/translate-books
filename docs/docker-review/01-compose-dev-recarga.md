# 01 · Desarrollar exige Python y Node en el equipo

- **Severidad:** Medio
- **Categoría:** Experiencia de desarrollo
- **Estado:** abierto
- **Ubicación:** `README.md` («Desarrollo local (sin Docker)»), `docker-compose.yml`, `frontend/Dockerfile`, `backend/Dockerfile`
- **Aceptación:** [01-compose-dev-recarga.aceptacion.md](01-compose-dev-recarga.aceptacion.md)

## Problema

Hoy los contenedores solo sirven builds de producción: cualquier cambio exige reconstruir imágenes (minutos con
el build de Next y la imagen del backend de 2,45 GB). Para iterar rápido hay que instalar en el host un `.venv`
(`pip install -e backend[dev]`) y `npm install`, más Tesseract, OCRmyPDF y Calibre si se toca el pipeline.

## Cómo reproducirlo

Seguir el README en un equipo limpio con solo Docker: la sección de desarrollo no funciona sin Python 3.12, Node 22 y paquetes del sistema.

## Impacto

Cada cambio cuesta un rebuild o una instalación local que diverge de la imagen (versiones de Tesseract, fuentes, Calibre).

## Corrección propuesta

Añadir `compose.dev.yml` (override) con: `api` con `uvicorn --reload` y `backend/` montado; `worker` con el código montado y reinicio sencillo (p. ej. `watchfiles` si ya está disponible por uvicorn[standard], o documentar `docker compose restart worker`); `frontend` con un target `dev` en el Dockerfile (`next dev`), `frontend/` montado y `node_modules` en un volumen anónimo. Mismos puertos que producción (3100/8000) y misma BD/volumen. Documentar `docker compose -f docker-compose.yml -f compose.dev.yml up` en el README y cómo volver al stack de producción.

## Notas

No cambiar el stack de producción salvo para añadir el target `dev` (el build de producción debe seguir igual). Next 16: leer `frontend/AGENTS.md` y `node_modules/next/dist/docs/` antes de tocar la config de desarrollo. El rewrite `/api` usa `BACKEND_URL` en tiempo de build; en dev se evalúa al arrancar `next dev`.
