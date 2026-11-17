# 11 · Varios parámetros de entrada son texto libre

- **Severidad:** Medio
- **Categoría:** Validación de entrada
- **Estado:** abierto
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
