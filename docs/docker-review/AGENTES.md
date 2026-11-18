# Reglas para el agente que cierra una ficha docker-review

Repo: `/home/andres/Documents/projects/personal/translate_books/traductor_libros`. Lee: este archivo, `README.md` de
esta carpeta, tu ficha `NN-*.md` y su `NN-*.aceptacion.md`, `CLAUDE.md`, la skill `.claude/skills/deploy/SKILL.md` y
las memorias de `/home/andres/.claude/projects/-home-andres-Documents-projects-personal-translate-books-traductor-libros/memory/`
(review-workflow, qa-verification, deploy-after-changes, goal-autonomy).

- Solo tu ficha. Otro problema → ficha nueva (siguiente NN libre, con su aceptación y su fila en el README), sin arreglarlo.
- El stack de producción (`docker compose up -d --build` / skill `deploy`) es el que mira el usuario en :3100: al
  terminar debe quedar arriba, sano y con la misma BD. Antes de reiniciar `api`/`worker`:
  `docker compose exec -T api python -m app.cli active-jobs` sin trabajos activos.
- Datos: nunca borrar ni sobrescribir `data/app.db` ni `data/outputs`/`data/uploads`. Si un cambio toca volúmenes o la
  BD, primero copia consistente (API de backup de sqlite3) a `data/app.db.bak-docker<NN>`. Pruebas de restauración,
  solo sobre copias.
- Tests: backend `ruff check app tests` + `pytest -q -m "not slow and not s3"` (190 passed como mínimo); frontend
  `tsc --noEmit`, `npm run lint`, `npm run test`, `npm run build`, `node ../handoff/check.mjs app lib`. Hasta que
  exista #02 se ejecutan en el host (`backend/.venv`, `npm` en `frontend/`); desde #02, en contenedor.
- Next 16: antes de tocar su configuración, lee `frontend/AGENTS.md` y `frontend/node_modules/next/dist/docs/`.
- No gastar DeepSeek ni cambiar los ajustes globales. No usar cuentas QA (no autorizadas): lo que solo se vea con
  sesión → «Pendiente de verificación manual: …». No leer ni copiar secretos de `.env` (solo nombres de variables).
- No añadir herramientas o dependencias nuevas (uv, poetry, pip-tools, imágenes base nuevas) salvo las imágenes ya
  usadas; si hace falta otra, termina y explícalo.
- [x] solo con evidencia y una línea indentada «  - Verificado: …»; si no se puede, [ ] con
  «  - Pendiente de verificación manual: …».
- Puertos libres para pruebas: no uses 3000 (otra app del usuario). `pkill -f patrón` mata su propia shell: usa PIDs.
- Commits en español «docker-review #NN: …» terminados en «Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>».
  Luego «Estado: resuelto · commit(s) `hash`» en la ficha y la fila del README a «resuelto» (vale un commit de docs).
  `frontend/next-env.d.ts` lo regenera Next: no lo incluyas salvo que la ficha lo pida. No hagas push.
- Decisiones: elige la opción recomendada (la más simple y segura), anótala en Notas y en el informe. Para si
  implicaría perder datos.

Informe final (máx. 15 líneas): qué cambió, hashes, comprobaciones, casillas pendientes y fichas nuevas.
