# traductor_libros

- La app que se revisa (`http://localhost:3100`, api en `:8000`) corre en Docker con builds de producción:
  los cambios de código no se ven hasta reconstruir. **Después de cambiar `frontend/` o `backend/`, usa la
  skill `deploy`** (`.claude/skills/deploy/SKILL.md`) antes de pedir al usuario que mire la página.
- Estilos del frontend: tokens y fichas en `handoff/` (`frontend/app/tokens.css` = `handoff/tokens.css`);
  comprobar con `node handoff/check.mjs frontend/app frontend/lib`.
