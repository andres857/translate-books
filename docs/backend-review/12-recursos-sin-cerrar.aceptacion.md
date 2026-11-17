# 12 · Aceptación: PDFs y sesiones de base de datos que no se cierran

Ficha: [12-recursos-sin-cerrar.md](12-recursos-sin-cerrar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `grep -n "pymupdf.open(" backend/app/api/*.py` muestra solo usos con `with`.
- [ ] `grep -n "SqlCache(SessionLocal())" backend/app` no devuelve resultados (la sesión de la caché se cierra).
- [ ] Test o medición: 200 peticiones a `/api/jobs/{id}/pages/1/preview` no aumentan los descriptores abiertos del proceso en más de 5 (anotar antes/después).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: la vista previa de páginas y la traducción/recomposición con el traductor falso siguen funcionando.
