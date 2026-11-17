# 02 · Enlaces a Configuración visibles para usuarios sin rol admin

- **Severidad:** Alto
- **Categoría:** Bug (permisos en UI)
- **Estado:** resuelto · commit `70e8ac8` · criterios verificados en [02-enlaces-configuracion-usuario.aceptacion.md](02-enlaces-configuracion-usuario.aceptacion.md)
- **Ubicación:** `frontend/app/components/upload-book.tsx:72` y `:147`
- **Aceptación:** [02-enlaces-configuracion-usuario.aceptacion.md](02-enlaces-configuracion-usuario.aceptacion.md)

## Problema

El formulario de subida enlaza a `/admin/settings` en dos sitios, sin mirar el rol:

- `:72`, aviso «El modo de traducción elegido aún no está listo. Revísalo en Configuración».
- `:147`, casilla de corrección del OCR: «Corregir errores del OCR con el modelo de Configuración».

Para un `user`, `routeFor` (`frontend/lib/auth.tsx:97`) redirige cualquier `/admin/*` a `/`.

## Cómo reproducirlo

Entrar como `user`, abrir «Subir un libro», elegir «Solo digitalizar» y pulsar el enlace «Configuración»: la página vuelve a «Libros» sin ningún mensaje.

## Impacto

El usuario recibe una instrucción que no puede cumplir y el enlace parece roto. Lo introdujo el login: antes todas las rutas eran accesibles.

## Corrección propuesta

Leer `isAdmin` de `useAuth()` en `UploadBook`: los admins ven el enlace; los demás ven texto plano («Avisa al administrador para revisarlo» / «el modelo configurado»).

## Notas

La barra lateral (`app/components/nav.tsx`) y `app/page.tsx` ya ocultan los enlaces de administración a los usuarios; este componente se quedó fuera.
