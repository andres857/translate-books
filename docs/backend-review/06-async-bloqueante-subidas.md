# 06 · Las subidas directas bloquean el event loop

- **Severidad:** Alto
- **Categoría:** Rendimiento (async)
- **Estado:** resuelto · commit(s) `c0b3ea9`
- **Ubicación:** `backend/app/api/routes_jobs.py:246-262` (`create_job`) y `backend/app/api/routes_files.py:328-336` (`upload_file`)
- **Aceptación:** [06-async-bloqueante-subidas.aceptacion.md](06-async-bloqueante-subidas.aceptacion.md)

## Problema

Las dos rutas son `async def`, pero tras `await file.read()` hacen trabajo **síncrono** en el event loop: abrir el
PDF con PyMuPDF (hasta `MAX_UPLOAD_MB`=200), calcular el SHA-256, escribir el archivo en disco, consultas de
SQLAlchemy síncronas y, en `/api/files`, la subida a S3 con boto3.

## Cómo reproducirlo

Test: lanzar en paralelo una subida grande a `POST /api/jobs` y un `GET /api/health`; hoy el health espera a
que termine la subida. Con uvicorn real: `curl` de un PDF de ~100 MB y medir la latencia de `/api/health` durante
la subida.

## Impacto

Mientras alguien sube un libro por la ruta de respaldo, el resto de usuarios (polling, login) se queda esperando: todas las peticiones comparten ese único loop.

## Corrección propuesta

Convertirlas en `def` (FastAPI las ejecuta en el threadpool) leyendo de `file.file`, o envolver la parte síncrona en `await run_in_threadpool(...)`. Mantener el límite de tamaño y los mensajes.

## Notas

La subida normal del frontend va por S3 prefirmado (`/presign` + `/from-upload`, que ya son `def`); estas rutas son el respaldo y la de archivos del admin.

Decisión al resolver: se eligió convertir las dos rutas en `def` (leyendo de `file.file`) en vez de
`run_in_threadpool`, por ser lo más simple: todo el handler, incluidas las dependencias síncronas y la subida a S3
de `/api/files`, va al threadpool. El análisis multipart (`request.form()`) lo hace Starlette en el event loop
antes de llamar al handler, por trozos y volcando a un temporal; es el resto de ~50 ms medido y no se toca aquí.
El frontend no necesita cambios: el contrato (campos, códigos y mensajes) es el mismo.
