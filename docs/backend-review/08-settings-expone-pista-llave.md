# 08 · Un usuario sin rol admin ve la pista de la llave de DeepSeek

- **Severidad:** Medio
- **Categoría:** Seguridad
- **Estado:** resuelto · commit(s) `1592a3c`
- **Ubicación:** `backend/app/api/routes_settings.py:376-378` (`GET /api/settings`, router con dependencia USER) y `backend/app/runtime_settings.py:41-47` (`public`)
- **Aceptación:** [08-settings-expone-pista-llave.aceptacion.md](08-settings-expone-pista-llave.aceptacion.md)

## Problema

`GET /api/settings` está disponible para cualquier sesión normal y devuelve `RuntimeSettings.public()`:
`deepseek_key_set`, `deepseek_key_hint` (los **4 últimos caracteres** de la llave), `deepseek_concurrency`,
`deepseek_thinking`, etc. El frontend del rol user solo lo usa para el rótulo del método (`methodLabel`, en
`frontend/app/page.tsx:41` y `components/nav.tsx`).

## Cómo reproducirlo

```bash
# con la cookie de qa-user
curl -s -H 'Cookie: tl_session=…' http://localhost:3100/api/settings | jq .deepseek_key_hint
```

## Impacto

Un usuario sin privilegios obtiene información de la configuración interna y parte del secreto; reduce la entropía de la llave y revela el proveedor y la concurrencia.

## Corrección propuesta

Para el admin, la vista completa como hoy; para el user, solo lo que pinta la UI (`provider`, `deepseek_model`, `deepseek_thinking` si `methodLabel` lo usa). **Cambia el contrato para el rol user**: comprobar `methodLabel` en `frontend/lib/api/settings.ts` y ajustar el tipo si hace falta.

## Notas

Decisión del usuario (16-nov-2026): para el rol user, `GET /api/settings` devuelve solo lo que pinta el rótulo
del método: `provider` y `deepseek_model`. `deepseek_thinking` tampoco se devuelve porque `methodLabel` no lo usa;
quedan fuera `deepseek_key_hint`, `deepseek_key_set`, `deepseek_concurrency` y `deepseek_models`. El admin conserva
la vista completa (`RuntimeSettings.public()`); el user recibe `RuntimeSettings.method()`. Es un cambio de contrato
para el rol user: en el frontend, `MethodSettings` + `getMethodSettings()` para la barra lateral y el inicio, y
`getSettings()` (vista completa) solo en la pantalla Configuración del admin.
