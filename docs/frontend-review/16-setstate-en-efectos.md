# 16 · setState síncrono dentro de efectos (20 casos)

- **Severidad:** Medio
- **Categoría:** Datos y estados (React)
- **Estado:** abierto
- **Ubicación:** 20 efectos en 9 archivos: `app/admin/jobs/[id]/compare.tsx` (4), `app/admin/jobs/[id]/page.tsx`, `app/admin/jobs/[id]/terms.tsx`, `app/admin/playground/history/page.tsx` (2), `app/admin/playground/page.tsx` (4), `app/admin/playground/panel.tsx` (2), `app/admin/playground/scope-view.tsx` (5), `lib/auth.tsx`
- **Aceptación:** [16-setstate-en-efectos.aceptacion.md](16-setstate-en-efectos.aceptacion.md)
- **Origen:** lo detectó ESLint al resolver el #14 (regla `react-hooks/set-state-in-effect` de `eslint-config-next` 16)

## Problema

Muchos efectos hacen `setState` en cuanto cambian sus dependencias: reinicios de vista al cambiar de página o
de libro (`setDrafts({})`, `setPages([])`, `setChapters([])`), lectura de preferencias de `localStorage` al
montar (`setShow`, `setSize`), copia de props a estado (`setDraftName(draft?.name)`) y cargas que llaman a
`load()`/`reload()`/`refresh()` directamente en el cuerpo del efecto.

## Cómo reproducirlo

`cd frontend && npx eslint . --rule '{"react-hooks/set-state-in-effect": "error"}'` → 20 errores.
Hoy la regla está en `warn` en `frontend/eslint.config.mjs` con un comentario que apunta aquí.

## Impacto

Renders en cascada (un render con el estado viejo y otro con el reiniciado) y parpadeos de contenido. Es
también la causa de fondo de errores como el #04/#05: el estado «de la página anterior» sobrevive un render.

## Corrección propuesta

Según el caso (ver «You might not need an effect» de React):
- reinicio de estado al cambiar una clave → `key={page}` en el componente o «ajustar estado durante el render»;
- preferencias de `localStorage` → inicializador perezoso de `useState` (con cuidado de la hidratación) o
  `useSyncExternalStore`;
- copia de props a estado → derivar en el render;
- cargas → el `setState` dentro del `.then` del efecto ya es correcto: mover la llamada síncrona inicial
  (p. ej. `setX(null)` antes de cargar) a donde cambia la clave.

## Notas

Tras el #11 quedan 19: el efecto inicial de `lib/auth.tsx` ya no consulta la sesión cuando llega del servidor.

Se corrige por archivos, con un commit cada uno. Cuando no quede ninguno, la regla vuelve a `error` en
`frontend/eslint.config.mjs`.
