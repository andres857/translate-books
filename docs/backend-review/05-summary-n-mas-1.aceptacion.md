# 05 · Aceptación: El resumen del admin hace una consulta por página

Ficha: [05-summary-n-mas-1.md](05-summary-n-mas-1.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo con `count_queries`: `GET /api/admin/jobs/{id}/summary` hace **≤ 8 queries** sea cual sea el número de páginas.
  - Verificado: `test_summary_queries_do_not_grow_with_pages` (tests/test_admin.py) en verde: mismas queries con las páginas del PDF de prueba y con 20 más (≤ 8) y una sola sentencia sobre `segments`; falla con el código anterior.
- [x] Test nuevo: los totales (`segments`, `edited`, `translated`, `min_scale` por página) coinciden con los de antes del cambio para el PDF de prueba.
  - Verificado: `test_summary_totals_match_per_page_computation` compara `pages` y `totals` con el cálculo anterior (recorriendo `page.segments`) sobre el PDF de prueba más 20 páginas de borde (sin bloques, `fit_scale` 0/NULL, traducción vacía, editados, acciones `keep`/`review`); pasa con el código anterior y con el nuevo.
- [x] Medición sobre una copia de la BD real: de 198 a ≤ 8 queries (anotar el número en «Verificado»).
  - Verificado (copia con la API de backup de sqlite3, `mode=ro`; 192 páginas, 3345 bloques): **198 → 6** queries (2 de sesión, trabajo, resumen agregado, páginas a revisar, documento). sha256 del JSON igual antes y después: `b551a7dfa79872ae428febd37660d239dca6c2903a65c2f1d996468fa827a728`.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 161 passed, 1 skipped, 5 deselected (antes 159 passed + 2 nuevos).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!` y `test_alembic_check` en verde (dentro de la suite).
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: `active-jobs` → «sin trabajos activos»; reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y el contenedor `api` contiene la consulta agregada (`func.min(case`).
- [ ] Regresión: la pantalla Resumen del admin muestra los mismos totales que antes para el libro QA.
  - Verificado (parte automática): el JSON del resumen del libro #1 es idéntico byte a byte (mismo sha256) sobre la copia de la BD real, y la pantalla consume solo ese JSON.
  - Pendiente de verificación manual: abrir la pantalla Resumen del admin en localhost:3100 con el libro QA (cuentas QA no autorizadas en esta tarea).
