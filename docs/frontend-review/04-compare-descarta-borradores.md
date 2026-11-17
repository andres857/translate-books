# 04 · Vista Libro: cambiar de página descarta las correcciones sin guardar

- **Severidad:** Medio
- **Categoría:** Bug (pérdida de datos)
- **Estado:** abierto
- **Ubicación:** `frontend/app/admin/jobs/[id]/compare.tsx:147-150` (efecto que hace `setDrafts({})`)
- **Aceptación:** [04-compare-descarta-borradores.aceptacion.md](04-compare-descarta-borradores.aceptacion.md)

## Problema

Al cambiar `page`, el efecto ejecuta `setDrafts({})` y recarga los bloques. Se cambia de página con ←/→
(`onKey`), con la rueda al llegar al borde de la hoja (`onWheel`), con el campo de página y con el índice,
y ninguno de esos caminos comprueba si hay borradores (`dirty`).

## Cómo reproducirlo

Como admin, en «Libro», editar la traducción de un bloque sin pulsar «Guardar» y girar la rueda sobre la hoja hasta el borde (o pulsar → fuera del campo): la página cambia y la corrección desaparece.

## Impacto

Se pierde trabajo de corrección con un gesto involuntario (un trackpad basta).

## Corrección propuesta

Si `dirty > 0`: bloquear el cambio de página automático (rueda y flechas) y pedir confirmación en los cambios explícitos (índice, campo de página), o conservar los borradores por página.

## Notas

La tecla ←/→ ya se ignora mientras el foco está en un `TEXTAREA`; el problema aparece al salir del campo.
