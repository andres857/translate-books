# 05 · Aceptación: El resumen del admin hace una consulta por página

Ficha: [05-summary-n-mas-1.md](05-summary-n-mas-1.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Test nuevo con `count_queries`: `GET /api/admin/jobs/{id}/summary` hace **≤ 8 queries** sea cual sea el número de páginas.
- [ ] Test nuevo: los totales (`segments`, `edited`, `translated`, `min_scale` por página) coinciden con los de antes del cambio para el PDF de prueba.
- [ ] Medición sobre una copia de la BD real: de 198 a ≤ 8 queries (anotar el número en «Verificado»).

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: la pantalla Resumen del admin muestra los mismos totales que antes para el libro QA.
