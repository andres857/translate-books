# 17 · El límite de intentos por IP es compartido por todos los usuarios

- **Severidad:** Alto
- **Categoría:** Seguridad / disponibilidad (backend)
- **Estado:** resuelto · commit `48f7dd2` · criterios verificados en [17-limite-login-ip-compartida.aceptacion.md](17-limite-login-ip-compartida.aceptacion.md)
- **Ubicación:** `backend/app/auth/rate_limit.py:39` (`login_buckets`), `backend/app/auth/sessions.py:58` (`client_ip`), `backend/app/api/routes_auth.py:63-64`
- **Aceptación:** [17-limite-login-ip-compartida.aceptacion.md](17-limite-login-ip-compartida.aceptacion.md)
- **Origen:** encontrado al verificar el #02 en el navegador (el login dejó de responder)

## Problema

El contador por IP usa `request.client.host`. En Docker, el navegador nunca habla con el api: el frontend
(Next) reenvía `/api/*`, así que todas las peticiones llegan con la IP del contenedor del frontend. Hay un solo
cubo `ip:<frontend>` de 10 intentos cada 15 minutos para todos los usuarios.

Además, el rewrite de Next no añade la IP del cliente: reenvía tal cual el `X-Forwarded-For` que mande el
navegador, que es falsificable.

## Cómo reproducirlo

Diez intentos de login (buenos o malos, de cualquier cuenta) en 15 minutos desde la web bloquean a todos:

```bash
curl -s -X POST localhost:3100/api/auth/login -H 'Origin: http://localhost:3100' \
  -H 'X-Requested-With: traductor' -H 'Content-Type: application/json' \
  -d '{"email":"nadie@astrobooks.local","password":"x"}' -D - -o /dev/null | grep -i '^HTTP\|retry-after'
# → HTTP/1.1 429 · retry-after: 701   (cubo ip:172.27.0.5 con 12 intentos)
```

Comprobado también que Next reenvía `X-Forwarded-For: 1.2.3.4` si lo manda el cliente y no envía ninguno si no.

## Impacto

Cualquiera puede bloquear el login de toda la app con 10 intentos. Con varios usuarios reales, el límite salta
solo en un día normal.

## Corrección propuesta

Nueva opción `TRUSTED_PROXIES` (IPs o redes separadas por comas). Cuando la conexión llega de un proxy de
confianza, la IP del cliente es desconocida: no se usa el cubo por IP y se mantienen el de correo y el total. No
se confía en `X-Forwarded-For`, porque Next no lo pone. En el compose, `TRUSTED_PROXIES` es la red interna de
Docker.

## Notas

Lo introdujo el login (commit `75406ce`). Si en el futuro hay un proxy delante de Next que ponga la IP real de
forma fiable, se podrá leer de su cabecera desde la lista de confianza.
