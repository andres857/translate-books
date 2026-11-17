# 01 · Redirección abierta en el `?next=` del login

- **Severidad:** Crítico
- **Categoría:** Seguridad
- **Estado:** abierto
- **Ubicación:** `frontend/lib/auth.tsx:31` (`safeNext`) y su uso en `frontend/lib/auth.tsx:115`
- **Aceptación:** [01-open-redirect-login.aceptacion.md](01-open-redirect-login.aceptacion.md)

## Problema

`safeNext` solo comprueba que el destino empiece por `/`, no por `//` ni por `/login`:

```ts
return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login") ? next : "/";
```

El navegador trata `\` como `/` en URLs `http(s)`, así que `/\evil.example` pasa el filtro y se resuelve
como `//evil.example`, es decir, otro origen. `URLSearchParams.get("next")` decodifica `%5C`, por lo que el
ataque cabe en un enlace normal.

## Cómo reproducirlo

Comprobado con Node (misma resolución de URL que el navegador):

```bash
node -e 'const s=n=>n&&n.startsWith("/")&&!n.startsWith("//")&&!n.startsWith("/login")?n:"/";
console.log(new URL(s("/\\evil.example"),"http://localhost:3100").href)'
# → http://evil.example/
```

En el navegador: abrir `http://localhost:3100/login?next=/%5Cevil.example`, iniciar sesión y observar la
navegación final (no se probó en un navegador real).

## Impacto

Un enlace legítimo al login de la app puede llevar al usuario, ya autenticado, a una página falsa que imite AstroBooks (phishing de credenciales).

## Corrección propuesta

Resolver el destino con `new URL(next, window.location.origin)` y aceptarlo solo si `url.origin` coincide con el de la app; devolver `url.pathname + url.search + url.hash`. Rechazar también `/login`. Añadir pruebas unitarias de `safeNext`.

## Notas

Lo introdujo el cambio del login (commit `75406ce`). El proxy (`frontend/proxy.ts`) genera `?next=` con `encodeURIComponent(pathname + search)`, que es un camino interno legítimo y debe seguir funcionando.
