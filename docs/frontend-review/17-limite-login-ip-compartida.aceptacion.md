# 17 · Aceptación: El límite de intentos por IP es compartido por todos los usuarios

Ficha: [17-limite-login-ip-compartida.md](17-limite-login-ip-compartida.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [ ] Prueba de backend: con la conexión desde un proxy de confianza, 11 intentos fallidos con correos distintos no devuelven 429 (no se usa el cubo por IP).
- [ ] Prueba de backend: desde una IP que no es de confianza, el 11.º intento devuelve 429 con `Retry-After` (el cubo por IP sigue funcionando).
- [ ] Prueba de backend: 11 intentos con el mismo correo a través del proxy devuelven 429 (el cubo por correo sigue funcionando).
- [ ] Prueba de backend: un `X-Forwarded-For` enviado por el cliente no cambia el cubo usado.
- [ ] En la app desplegada, tras 10 intentos fallidos con `nadie@astrobooks.local` por `:3100`, otra cuenta puede iniciar sesión (200).
- [ ] `docker compose exec -T api python -c '…AuthRateLimit…'` no muestra ningún cubo `ip:` con la IP del frontend después de logins por `:3100`.

## Comprobaciones comunes

- [ ] `cd backend && python -m pytest -q -m "not slow and not s3"` en verde.
- [ ] `cd frontend && npm run test:e2e` en verde (el login por la web sigue funcionando).
- [ ] Regresión: login, logout y límite de intentos en la cuenta de prueba.
