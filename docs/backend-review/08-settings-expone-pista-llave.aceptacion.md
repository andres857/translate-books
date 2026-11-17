# 08 · Aceptación: Un usuario sin rol admin ve la pista de la llave de DeepSeek

Ficha: [08-settings-expone-pista-llave.md](08-settings-expone-pista-llave.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo: como `user`, `GET /api/settings` no incluye `deepseek_key_hint`, `deepseek_key_set` ni `deepseek_concurrency`.
- [ ] Test nuevo: como `admin`, la respuesta sigue teniendo todos los campos actuales.
- [ ] En la app desplegada como qa-user: la cabecera/inicio sigue mostrando el método de traducción (captura o texto anotado en «Verificado»).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: la pantalla Configuración del admin y el rótulo del método para el user siguen funcionando.
