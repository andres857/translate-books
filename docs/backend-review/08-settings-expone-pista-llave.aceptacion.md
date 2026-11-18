# 08 · Aceptación: Un usuario sin rol admin ve la pista de la llave de DeepSeek

Ficha: [08-settings-expone-pista-llave.md](08-settings-expone-pista-llave.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: como `user`, `GET /api/settings` no incluye `deepseek_key_hint`, `deepseek_key_set` ni `deepseek_concurrency`.
  - Verificado: `test_user_settings_view_hides_key_hint` (respuesta exactamente `{provider, deepseek_model}`, sin la pista «abcd») en verde; falla sin la corrección.
- [x] Test nuevo: como `admin`, la respuesta sigue teniendo todos los campos actuales.
  - Verificado: `test_admin_settings_view_keeps_all_fields` (los 7 campos de antes, con `deepseek_key_hint == "abcd"`) en verde.
- [x] En la app desplegada como qa-user: la cabecera/inicio sigue mostrando el método de traducción (captura o texto anotado en «Verificado»).
  - Verificado (app desplegada): Chrome como qa-user: la barra lateral muestra «API · deepseek-flash» y el inicio «Método: API · deepseek-flash»; `GET /api/settings` como user → 200 `{"provider":"deepseek","deepseek_model":"deepseek-flash"}` (sin `deepseek_key_hint`).

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 154 passed, 1 skipped, 5 deselected (antes 152 passed + 2 nuevos). Frontend: `tsc --noEmit`, `lint`, `test` (20 passed), `build` y `handoff/check.mjs` (0 problemas) en verde.
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado (al cerrar el #15, sobre el código actual): `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos, reconstruidos `api`, `worker` y `frontend`; health `{"ok":true}`, `/login` 200, el contenedor `api` contiene `RuntimeSettings.method` y `GET /api/settings` sin sesión sigue en 401.
- [x] Regresión: la pantalla Configuración del admin y el rótulo del método para el user siguen funcionando.
  - Verificado (parte automática): `test_settings_api` y `test_admin_settings_view_keeps_all_fields` en verde (el admin sigue recibiendo la vista completa que usa `settings-form.tsx`).
  - Verificado (app desplegada): Chrome como qa-admin: /admin/settings se ve completa (API de DeepSeek, llave, modelo, razonamiento; 4 campos) sin guardar nada, y `/api/settings` como admin trae los 7 campos (incl. `deepseek_key_hint`); como qa-user el rótulo «API · deepseek-flash» en la barra y el inicio (casilla de arriba).
