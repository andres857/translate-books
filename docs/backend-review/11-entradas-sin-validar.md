# 11 · Varios parámetros de entrada son texto libre

- **Severidad:** Medio
- **Categoría:** Validación de entrada
- **Estado:** resuelto · commit(s) `c35ac2d`
- **Ubicación:** `backend/app/api/routes_terms.py:165-168` (`TermIn.category`), `backend/app/api/routes_playground.py:27-31` (`DraftIn.task`), `:143-160` (`VariantIn`, `ScopeIn.scope`, `ScopeIn.pages`), `backend/app/api/routes_jobs.py:414` (`format`), `:472` (`version`), `:269-282` (`FromUploadIn.mode`, idiomas)
- **Aceptación:** [11-entradas-sin-validar.aceptacion.md](11-entradas-sin-validar.aceptacion.md)

## Problema

Ejemplos:

- `TermIn.category` acepta cualquier cadena y se guarda en mayúsculas (`body.category.upper()`); la columna es
  `String(16)` y SQLite no la limita.
- `ScopeIn.pages` y `VariantIn.model`/`prompt_name` no tienen `max_length`.
- `version` en la vista previa: cualquier valor distinto de `original` muestra la traducción.
- `mode`, `ocr_lang`, `source_lang` se validan a mano dentro de la función, con mensajes 400 distintos de los 422
  del resto.

## Cómo reproducirlo

`POST /api/protected-terms {"term":"Sol","category":"cualquier-cosa-larguísima"}` → 200 y se guarda tal cual.

## Impacto

Datos incoherentes en la BD (categorías que la UI no sabe pintar) y cargas de texto arbitrariamente grandes.

## Corrección propuesta

`Literal[...]` para los enumerados (category, task, scope, format, version, mode, ocr_lang) y `Field(max_length=…)` en textos; dejar que FastAPI responda 422 con el formato ya definido en `main.py` (sin eco del valor).

## Notas

Cambia el código de error de algunos casos (400 → 422). Revisar que el frontend trate ambos igual (`ApiError`).

Cierre (17-nov-2026), decisiones con la opción recomendada:

- **Categorías de términos:** `NAME`, `BRAND`, `CODE`, `TERM`, las que ofrece y pinta la vista de términos
  (`frontend/app/admin/jobs/[id]/terms.tsx`, `CATEGORY`); el Protector usa `NAME` por defecto. Solo letras a
  propósito: la categoría forma el marcador `__CATEGORIA_000__` y `PLACEHOLDER_RE` solo reconoce `[A-Z]+`.
  Se sigue aceptando en minúsculas (`"term"` → `TERM`, como hacía `.upper()`). La BD real no tiene términos
  protegidos, así que no hay filas antiguas fuera de la lista.
- **Topes:** `ScopeIn.pages` 2000, `RunIn.chapter` 512, `VariantIn.model` 64, `provider`/`thinking`/`prompt` 32,
  `prompt_name` 120 (igual que el nombre del borrador), `source_lang`/`target_lang` 8 (la columna es `String(8)`).
- **Validado por FastAPI (422):** `category`, `DraftIn.task`, `scope`, `format`, `version`, `mode`, `ocr_lang`. Se
  quitan las comprobaciones a mano de `mode` y `ocr_lang` y el 400 de formato desconocido. `ocr_lang` se valida
  ahora también fuera de «digitize» (el frontend siempre manda `en`/`es`/`auto`). Siguen en 400 las reglas que no
  son de forma: idiomas distintos de en→es, borrador sin tarea/nombre/texto, páginas fuera del libro, variantes.
- **Frontend sin cambios:** `parse()` (`frontend/lib/api/http.ts`) trata igual cualquier estado no-ok y usa el
  `message` del cuerpo (el 422 trae «Los datos enviados no son válidos.»); `DownloadLink` y las vistas de términos y
  Playground solo envían valores de las listas. El único caso que distingue 400 (`upload.ts`, presign) no cambia.
