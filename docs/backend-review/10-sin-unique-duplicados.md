# 10 · Nada en la BD impide duplicados en bloques, glosario y términos

- **Severidad:** Medio
- **Categoría:** Integridad
- **Estado:** resuelto · commit(s) `a27ede6`
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

Cierre (16-nov-2026), decisiones tomadas con la opción recomendada:

- **Índices únicos, no constraints:** `CREATE UNIQUE INDEX` en la migración `e1f3a5c7b9d2` (SQLite no reconstruye
  tablas) y los mismos `Index(..., unique=True)` en los modelos. `alembic check` no puede comparar en SQLite los
  índices de expresiones (avisa y los omite); se comprobó a mano que el DDL de los modelos y el de la migración es igual.
- **Términos protegidos con mayúsculas:** el índice es `(coalesce(document_id, 0), term)` como proponía la ficha,
  no `lower(term)`: el `Protector` compara distinguiendo mayúsculas («MC» y «mc» protegen cosas distintas). El
  glosario sí usa `lower(source)`, igual que `effective_glossary`/`save_auto`.
- **Global y por libro conviven:** el mismo término puede estar global y en un libro (claves 0 y `document_id`); es
  lo que ya permitía el glosario efectivo. No hay `documents.id = 0`.
- **Manual sobre auto del mismo libro:** añadir a mano un término que ya está como «auto» en ese libro da 409; para
  cambiarlo se edita la entrada (PATCH la pasa a manual), como indica la nota anterior.
- **`lower()` de SQLite solo pliega ASCII:** «Éter» y «éter» no chocan en el índice (Python sí las considera iguales
  en `save_auto`). Se acepta: es más laxo, nunca rechaza algo que el código considere distinto.
- **409 genérico:** `_commit_new` hace rollback y responde «Ese término ya existe.» `from None`, sin el texto de la
  BD. `PATCH /api/glossary/{id}` no cambia `source`, así que no necesita el mismo tratamiento.
