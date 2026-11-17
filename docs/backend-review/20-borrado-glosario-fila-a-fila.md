# 20 · Al borrar un libro, glosario, términos e intentos se borran fila a fila

- **Severidad:** Bajo
- **Categoría:** Rendimiento
- **Estado:** abierto
- **Ubicación:** `backend/app/playground.py` (`delete_job`: bucles sobre `PlaygroundAttempt`, `GlossaryEntry` y `ProtectedTerm`)
- **Aceptación:** [20-borrado-glosario-fila-a-fila.aceptacion.md](20-borrado-glosario-fila-a-fila.aceptacion.md)

## Problema

Tras #09 las páginas y los bloques se borran en la BD (ON DELETE CASCADE), pero `delete_job` sigue cargando y
borrando con `s.delete()` una a una las entradas del glosario y los términos del documento (cuando es su último
trabajo) y los intentos del Playground: un SELECT y un DELETE por fila.

## Cómo reproducirlo

Con `count_queries`: borrar (`DELETE /api/jobs/{id}`) un trabajo cuyo documento tiene 1 entrada de glosario y otro
con 50; el número de queries crece con las entradas. En la BD real serían ~149 DELETE del glosario.

## Impacto

Menor que el de #09 (cientos de filas, no miles), pero el borrado sigue dependiendo del tamaño del glosario y de
los intentos y retiene el bloqueo de escritura algo más.

## Corrección propuesta

`delete(GlossaryEntry).where(document_id == doc.id)` y lo mismo para `ProtectedTerm`; para los intentos, leer solo
la columna `pdf` (`select(PlaygroundAttempt.pdf)`) y borrar con un `delete()` por `job_id`. Sin cambio de esquema.

## Notas

Detectado al cerrar #09 (fuera de su alcance: la ficha y su criterio solo cubren páginas y bloques).

- Decisión: `delete(...)` en bloque recogiendo antes solo las rutas (`select(PlaygroundRun.id)` para las carpetas
  `run_<id>` y `select(PlaygroundAttempt.pdf)` para los PDF), en el mismo orden de rutas que antes; los archivos se
  siguen borrando después del commit (`jobs_service.delete_job_and_files`). Qué se borra no cambia.
- Decisión: las evaluaciones (`PlaygroundRun`) también pasan a un `delete()` por `job_id`, porque el bucle
  `s.delete(r)` era el mismo patrón fila a fila en la misma función y ya solo hacía falta su id. Orden en la BD:
  intentos → evaluaciones → trabajo (RESTRICT de #09) → glosario y términos → documento.
- `count_queries` cuenta un executemany como una sentencia, así que el ORM ya agrupaba los DELETE por id: el test
  comprueba también que esas tablas solo aparecen en un DELETE por `document_id`/`job_id`.
- Sin cambios en el contrato de la API: el frontend no necesita ajuste.
