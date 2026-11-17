# 11 · Aceptación: Varios parámetros de entrada son texto libre

Ficha: [11-entradas-sin-validar.md](11-entradas-sin-validar.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Test nuevo: `category` fuera de la lista → 422; dentro de la lista → 200.
  - Verificado: `test_protected_term_category_must_be_known` (`cualquier-cosa-larguísima` → 422 `literal_error` en `["body","category"]`; `BRAND` y `code` → 200 y se guardan `BRAND`/`CODE`).
- [x] Test nuevo: `format=docx` en la descarga y `version=otra` en la vista previa → 422.
  - Verificado: `test_download_format_and_preview_version_are_closed_lists`; además `format=mobi` pasa de 400 a 422 en `test_admin.py`, y `test_upload_mode_and_ocr_lang_are_closed_lists` (mode/ocr_lang → 422 sin crear trabajo).
- [x] Test nuevo: `ScopeIn.pages` con más de 2000 caracteres → 422.
  - Verificado: `test_playground_inputs_are_validated` (2002 caracteres → 422 en `["body","pages"]`; también `scope` desconocido y `model` de 65). La tarea `x` del borrador pasa de 400 a 422 en `test_playground.py::test_api`.
- [x] Los 422 no repiten el valor recibido (cuerpo con `errors[].loc` y `type` solamente).
  - Verificado: los cuatro tests nuevos comprueban `errors == [{loc, type}]` y que el valor enviado no aparece en el cuerpo.

## Comprobaciones comunes

- [x] `cd backend && .venv/bin/python -m pytest -q -m "not slow and not s3"` termina en verde (ningún test que pasaba antes falla; los nuevos de esta ficha pasan).
  - Verificado: 177 passed, 1 skipped, 5 deselected (antes 173 passed + 4 nuevos; dos asserts 400 → 422 por el cambio de contrato).
- [x] Si la ficha añade una migración: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` sin errores sobre una **copia** de `data/app.db`, y `PRAGMA foreign_key_check` vacío después. Si no migra, escribir «sin migración».
  - Verificado: sin migración.
- [x] Desde que exista el #15: `ruff check app tests` sin errores y el test de `alembic check` en verde.
  - Verificado: `ruff check app tests` → `All checks passed!`; `test_alembic_check` en verde dentro de la suite.
- [x] Desplegado con la skill `deploy`: `curl -s localhost:8000/api/health` devuelve `{"ok":true}` y `http://localhost:3100/login` responde 200.
  - Verificado: sin trabajos activos, reconstruidos `api` y `worker`; health `{"ok":true}`, `/login` 200 y el contenedor `api` contiene `TermCategory`.
- [ ] Regresión: Glosario y términos, Playground (estimar y ejecutar con prueba sin API) y descargas siguen funcionando.
  - Verificado (parte automática): tests de glosario/términos (`test_admin.py`, `test_glossary.py`), Playground con variante `fake` (`test_api`, `test_playground_compose.py`) y descargas PDF/EPUB/AZW3 en verde.
  - Pendiente de verificación manual: recorrer Glosario y términos, Playground y descargas en localhost:3100 (cuentas QA no autorizadas en esta tarea).
