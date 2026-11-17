# 19 · Tras el cambio obligatorio de contraseña no se llega a Libros

- **Severidad:** Bajo
- **Categoría:** Bug (flujo de login)
- **Estado:** resuelto · commit `b5fcb48` · criterios verificados en [19-cambio-obligatorio-no-lleva-a-libros.aceptacion.md](19-cambio-obligatorio-no-lleva-a-libros.aceptacion.md)
- **Ubicación:** `frontend/app/change-password/page.tsx` (`submit`) y `frontend/lib/auth.tsx` (`routeFor`)
- **Aceptación:** [19-cambio-obligatorio-no-lleva-a-libros.aceptacion.md](19-cambio-obligatorio-no-lleva-a-libros.aceptacion.md)
- **Origen:** encontrado en la regresión final del README («cambio obligatorio de contraseña»)

## Problema

Tras entrar con una contraseña temporal y elegir una nueva, la sesión pasa a normal y `routeFor` permite
`/change-password` a las sesiones normales (es también el cambio voluntario). Nadie redirige, así que el
usuario se queda en «Cambiar contraseña», ahora con la barra lateral y el formulario normal, aunque el comentario
de `submit` dice «si venía de una temporal, AppShell lleva a Libros».

## Cómo reproducirlo

Como admin, «Contraseña temporal» para una cuenta; entrar con ella → `/change-password` → guardar una nueva →
la URL sigue en `/change-password` y el título es «Cambiar contraseña».

## Impacto

Parece que el cambio no se aplicó o que hay que repetirlo.

## Corrección propuesta

En `submit`, si la sesión era restringida (cambio obligatorio), navegar a Libros tras `accept()`.
