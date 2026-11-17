# 13 · Aceptación: Borrado duplicado, imports internos y consultas al estilo 1.x

Ficha: [13-logica-duplicada-y-legacy.md](13-logica-duplicada-y-legacy.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] `grep -rn "\.query(" backend/app` no devuelve resultados.
- [ ] `grep -rn "_job_or_404" backend/app` solo aparece en su módulo (o se ha sustituido por la función pública).
- [ ] La lógica de borrado está en un solo sitio: `grep -n "remove_path" backend/app/api/*.py` no aparece en las rutas.
- [ ] Todos los tests de borrado y de autorización existentes siguen en verde sin cambiarlos.

## Comprobaciones comunes

- [ ] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
- [ ] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
- [ ] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
- [ ] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
- [ ] Regresión: borrar un libro desde Inicio (admin) y desde el Playground sigue funcionando.
