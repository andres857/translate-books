# 11 · Todas las páginas son de cliente: el HTML del servidor solo trae «Cargando…»

- **Severidad:** Medio
- **Categoría:** Frontera servidor/cliente
- **Estado:** abierto
- **Ubicación:** Las 10 `page.tsx` con `"use client"`; `frontend/app/components/app-shell.tsx` (no renderiza nada hasta conocer la sesión)
- **Aceptación:** [11-todo-en-cliente.aceptacion.md](11-todo-en-cliente.aceptacion.md)

## Problema

Todas las páginas cargan sus datos en `useEffect` tras hidratar, y `AppShell` muestra «Cargando…» hasta que `/api/auth/me` responde. El HTML del servidor no contiene contenido. Cada navegación sigue una cascada: JS → sesión → datos de la página → (a veces) datos dependientes.

## Cómo reproducirlo

`curl -s -b 'tl_session=<token>' localhost:3100/ | grep -c 'Libros subidos'` → `0`: el contenido no está en el HTML. DevTools › Network, recarga en `/`: `me` y `jobs` van en serie después de los scripts.

## Impacto

Pantalla de carga en cada recarga y más latencia percibida. Para una herramienta interna no es grave, pero es la mayor deuda estructural.

## Corrección propuesta

Migración gradual: (1) leer la sesión en el servidor (layout de servidor que llama a `/api/auth/me` con la cookie de la petición) y pasarla al `AuthProvider` como estado inicial; (2) convertir las páginas simples (Usuarios, Configuración, detalle del trabajo) en Server Components que cargan los datos y delegan lo interactivo a componentes cliente pequeños.

## Notas

Requiere decisión: cambia la arquitectura y conviene hacerlo después del #14 (ESLint y smoke tests). El backend se alcanza dentro de Docker en `http://api:8000` (`BACKEND_URL`).
