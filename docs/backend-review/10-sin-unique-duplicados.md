# 10 · Nada en la BD impide duplicados en bloques, glosario y términos

- **Severidad:** Medio
- **Categoría:** Integridad
- **Estado:** abierto
- **Ubicación:** `backend/app/db/models.py:84-110` (Segment), `:114-131` (ProtectedTerm, GlossaryEntry); `backend/app/api/routes_terms.py:203-238`
- **Aceptación:** [10-sin-unique-duplicados.aceptacion.md](10-sin-unique-duplicados.aceptacion.md)

## Problema

- `(page_id, seg_key)` debería ser único (una clave repetida hace que una traducción pise otra); hoy solo lo
  garantiza `ensure_unique_keys` en Python.
- `POST /api/glossary` y `POST /api/protected-terms` insertan sin comprobar si ya existe el mismo término para
  ese libro (o global): el admin puede crear dos entradas para «Ascendant» con traducciones distintas.

Los datos actuales no tienen duplicados (comprobado con `GROUP BY … HAVING COUNT(*) > 1`).

## Cómo reproducirlo

```bash
# dos veces seguidas, como admin
POST /api/glossary {"source":"Ascendant","target":"Ascendente"}
GET /api/glossary  → dos filas con source "Ascendant"
```

## Impacto

Con dos traducciones para el mismo término, el glosario efectivo elige una según el orden del diccionario; el resultado de la traducción depende de detalles no visibles.

## Corrección propuesta

Migración con índices únicos: `UNIQUE(page_id, seg_key)`; para glosario y términos, índice único sobre `(coalesce(document_id, 0), lower(source))` / `(coalesce(document_id, 0), term)` (SQLite admite índices sobre expresiones). En las rutas, `IntegrityError` → 409 «Ese término ya existe» sin filtrar el mensaje de la BD.

## Notas

`save_auto` ya evita duplicados al guardar lo descubierto; las entradas `auto` y `manual` comparten la regla (lo manual gana), así que el índice debe abarcar ambas.
