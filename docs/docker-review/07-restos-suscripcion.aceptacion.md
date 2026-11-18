# 07 · Aceptación: Quedan restos del modo de suscripción de Claude retirado

Ficha: [07-restos-suscripcion.md](07-restos-suscripcion.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Se documenta en las Notas si `data/settings.json` tiene claves `claude_*` (solo nombres) y cuántos `playground_attempts`/`playground_runs` tienen `provider = 'claude'` (consultas en solo lectura).
- [ ] `grep -rniE "claude|suscrip" backend/app frontend/app frontend/lib` no devuelve nada, o solo lo justificado en Notas.
- [ ] Los tests de ajustes y Playground siguen en verde.

## Comprobaciones comunes

- [ ] Backend: `ruff check app tests` limpio y `pytest -q -m "not slow and not s3"` en verde (190 passed o más), ejecutados con el método vigente (host `.venv` hasta que exista #02; desde #02, en contenedor).
- [ ] Frontend, si se tocó: `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build` y `node ../handoff/check.mjs app lib` en verde.
- [ ] `docker compose config -q` sin errores (y `docker compose -f docker-compose.yml -f compose.dev.yml config -q` desde que exista #01).
- [ ] Desplegado con la skill `deploy` (stack de producción): los servicios en `docker compose ps` están `running`/`healthy`, `curl -s localhost:8000/api/health` → `{"ok":true}` y `http://localhost:3100/login` → 200.
- [ ] El libro #1 sigue intacto (192 páginas, 3345 bloques, leído en solo lectura) y `data/app.db` no perdió filas.
- [ ] Regresión: Configuración del admin muestra el método actual y el historial del Playground se abre.
