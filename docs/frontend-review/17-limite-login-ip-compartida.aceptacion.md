# 17 · Aceptación: El límite de intentos por IP es compartido por todos los usuarios

Ficha: [17-limite-login-ip-compartida.md](17-limite-login-ip-compartida.md). Marca cada casilla (`- [x]`) solo después de comprobar el resultado indicado.

## Criterios

- [x] Prueba de backend: con la conexión desde un proxy de confianza, 11 intentos fallidos con correos distintos no devuelven 429 (no se usa el cubo por IP).
  - Verificado: `test_trusted_proxy_does_not_share_ip_bucket`: 11 intentos desde 172.27.0.5 con TRUSTED_PROXIES=172.16.0.0/12 → todos 401 y ningún cubo `ip:172.27.0.5`.
- [x] Prueba de backend: desde una IP que no es de confianza, el 11.º intento devuelve 429 con `Retry-After` (el cubo por IP sigue funcionando).
  - Verificado: `test_untrusted_ip_still_limited`: desde 203.0.113.9 el 11.º intento → 429 con `Retry-After` > 0.
- [x] Prueba de backend: 11 intentos con el mismo correo a través del proxy devuelven 429 (el cubo por correo sigue funcionando).
  - Verificado: `test_email_bucket_still_applies_behind_proxy`: 11 intentos a victima@ a través del proxy → 429.
- [x] Prueba de backend: un `X-Forwarded-For` enviado por el cliente no cambia el cubo usado.
  - Verificado: `test_client_forwarded_for_is_ignored`: con `X-Forwarded-For: 198.51.100.7` el cubo usado es `ip:203.0.113.20` (count 1) y no existe `ip:198.51.100.7`.
- [x] En la app desplegada, tras 10 intentos fallidos con `nadie@astrobooks.local` por `:3100`, otra cuenta puede iniciar sesión (200).
  - Verificado: en :3100, 10 intentos con nadie@astrobooks.local (el 10.º ya 429 por su propio cubo de correo) y luego qa-user → `login de otra cuenta: 200`.
- [x] `docker compose exec -T api python -c '…AuthRateLimit…'` no muestra ningún cubo `ip:` con la IP del frontend después de logins por `:3100`.
  - Verificado: tras 11 logins por :3100 el cubo `ip:172.27.0.5` sigue en 12 con su ventana de 02:06 (de antes del despliegue; no se incrementa) y no aparece ningún cubo `ip:` nuevo. La fila antigua no se borra: expira por ventana.

## Comprobaciones comunes

- [x] `cd backend && python -m pytest -q -m "not slow and not s3"` en verde.
  - Verificado: `pytest -q -m "not slow and not s3"` → `138 passed, 1 skipped`.
- [x] `cd frontend && npm run test:e2e` en verde (el login por la web sigue funcionando).
  - Verificado: `npm run test:e2e` como qa-user tras el despliegue → `1 passed`.
- [x] Regresión: login, logout y límite de intentos en la cuenta de prueba.
  - Verificado: login y logout por la web (smoke test) y límite de intentos (pruebas de backend y prueba en :3100) correctos.
