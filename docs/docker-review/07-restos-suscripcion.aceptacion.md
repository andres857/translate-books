# 07 · Aceptación: Quedan restos del modo de suscripción de Claude retirado

Ficha: [07-restos-suscripcion.md](07-restos-suscripcion.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Se documenta en las Notas si `data/settings.json` tiene claves `claude_*` (solo nombres) y cuántos `playground_attempts`/`playground_runs` tienen `provider = 'claude'` (consultas en solo lectura).
  - Verificado: Notas de la ficha: sin claves `claude_*`; 0 de 0 `playground_attempts` y 0 de 0 `playground_runs` con `provider = 'claude'` (sqlite `mode=ro`).
- [x] `grep -rniE "claude|suscrip" backend/app frontend/app frontend/lib` no devuelve nada, o solo lo justificado en Notas.
  - Verificado: el `grep` no devuelve nada (código de salida 1).
- [x] Los tests de ajustes y Playground siguen en verde.
  - Verificado: `pytest -q tests/test_settings.py tests/test_playground.py` → 26 passed.

## Comprobaciones comunes

- [x] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
  - Verificado (host `.venv`): `ruff check app tests` → All checks passed!; `pytest -q -m "not slow and not s3"` → 190 passed, 1 skipped.
- [x] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
  - Verificado: `tsc --noEmit` sin errores, `npm run lint` sin errores, `npm run test` 20 passed, `npm run build` correcto, `check.mjs app lib` → Problemas: 0.
- [x] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
  - Verificado: sin salida ni errores (#01 aún no existe).
- [x] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
  - Verificado: `active-jobs` → sin trabajos activos; `docker compose up -d --build`; `ps`: api y seaweedfs healthy, frontend, worker y cdn running (frontend sin healthcheck, ficha #03); health → `{"ok":true}`; `/login` → 200; el build servido no contiene «Suscripci» (0 archivos en `/app/.next`) y la api sirve el comentario nuevo.
- [x] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
  - Verificado: job 1 con 192 páginas y 3345 segmentos; recuento por tabla antes/después del deploy sin pérdidas (mode=ro).
- [ ] Regresión: Configuración del admin muestra el método actual y el historial del Playground se abre.
  - Pendiente de verificación manual: requiere sesión de admin (sin cuentas QA autorizadas): abrir Configuración y Playground → Historial en :3100.
