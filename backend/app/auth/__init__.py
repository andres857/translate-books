"""Login con correo y contraseña, sesiones opacas revocables en BD y dos roles (admin, user).

- Contraseñas: Argon2id (passwords.py).
- Sesión: cookie HttpOnly/SameSite=Strict con 32 bytes aleatorios; la BD guarda solo su SHA-256 (sessions.py).
- Escrituras: Origin exacto + X-Requested-With + X-CSRF-Token ligado a la sesión (deps.verify_write).
"""
