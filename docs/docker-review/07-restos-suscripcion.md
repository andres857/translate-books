# 07 · Quedan restos del modo de suscripción de Claude retirado

- **Severidad:** Bajo
- **Categoría:** Limpieza
- **Estado:** resuelto · commit(s) `151bd02`
- **Ubicación:** `backend/app/runtime_settings.py:84,87`, `backend/app/playground.py:45` (comentario), `frontend/app/admin/playground/shared.ts:35`
- **Aceptación:** [07-restos-suscripcion.aceptacion.md](07-restos-suscripcion.aceptacion.md)

## Problema

El modo de traducción con la suscripción de Claude se retiró, pero quedan: la lectura que ignora claves `claude_*` y
reescribe `provider` a `deepseek` en ajustes antiguos, un comentario sobre «suscripción» y un rótulo para el historial
del Playground con `provider == "claude"`.

## Cómo reproducirlo

`grep -rniE "claude|suscrip" backend/app frontend/app frontend/lib`.

## Impacto

Código muerto que confunde; sin impacto funcional mientras no queden ajustes ni historial antiguos.

## Corrección propuesta

Comprobar en la BD real (solo lectura) y en `data/settings.json` (solo leer los nombres de claves, nunca imprimir la llave) si quedan datos antiguos: si no hay `claude_*` ni intentos con `provider = 'claude'`, quitar los restos; si los hay, conservar solo lo necesario para leerlos y anotarlo.

## Notas

- Datos antiguos (solo lectura, 17-nov-2026): `data/settings.json` tiene solo `provider` (= `deepseek`) y claves
  `deepseek_*`; ninguna `claude_*`. `playground_attempts` y `playground_runs` están vacías (0 filas; 0 con
  `provider = 'claude'` en `config`/`variants`). No hay nada antiguo que leer, así que se quitan los restos.
- Decisión (recomendada, la más segura): se conservan los dos guardas genéricos de `runtime_settings.load()`
  —ignorar claves desconocidas y volver a `deepseek` si `provider` no es válido— con comentarios neutros, porque sin
  ellos un `settings.json` editado a mano impediría guardar ajustes (`validate` fallaría siempre). Se quita el rótulo
  «Suscripción de Claude (retirado)» de `variantName` y la «suscripción» del comentario de `CONFIRM_BLOCKS`.
- Los tests que siguen nombrando `claude` (`test_settings.py`, `test_playground.py`) comprueban que el modo
  retirado se rechaza y que un ajuste viejo se lee bien; quedan fuera del `grep` (solo `app`/`lib`) y se mantienen.
