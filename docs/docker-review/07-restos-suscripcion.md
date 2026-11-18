# 07 · Quedan restos del modo de suscripción de Claude retirado

- **Severidad:** Bajo
- **Categoría:** Limpieza
- **Estado:** abierto
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
