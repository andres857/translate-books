# 11 · Aceptación: Varios parámetros de entrada son texto libre

Ficha: [11-entradas-sin-validar.md](11-entradas-sin-validar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: `category` fuera de la lista → 422; dentro de la lista → 200.
- [ ] Test nuevo: `format=docx` en la descarga y `version=otra` en la vista previa → 422.
- [ ] Test nuevo: `ScopeIn.pages` con más de 2000 caracteres → 422.
- [ ] Los 422 no repiten el valor recibido (cuerpo con `errors[].loc` y `type` solamente).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: Glosario y términos, Playground (estimar y ejecutar con prueba sin API) y descargas siguen funcionando.
