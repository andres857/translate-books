# 05 · `.env` y `.env.example` mezclan valores del modo host con los de Docker

- **Severidad:** Bajo
- **Categoría:** Configuración
- **Estado:** resuelto · commit(s) `42b0b22`
- **Ubicación:** `.env.example`, `.env` (local, no versionado), `docker-compose.yml` (`x-backend.environment`)
- **Aceptación:** [05-env-valores-modo-host.aceptacion.md](05-env-valores-modo-host.aceptacion.md)

## Problema

`.env` contiene `DATABASE_URL=sqlite:///./data/app.db`, `DATA_DIR=./data` y `S3_ENDPOINT=http://localhost:8333`, que
solo valen fuera de Docker; el compose los sobrescribe en `environment`. Quien lea `.env` no sabe qué valor se usa
realmente en el contenedor.

## Cómo reproducirlo

`docker compose config | grep -E 'DATABASE_URL|S3_ENDPOINT'` frente a `.env`: los valores efectivos no son los del archivo.

## Impacto

Confusión al cambiar puertos u orígenes (CORS, S3), y errores difíciles de diagnosticar si alguien quita la sobrescritura del compose.

## Corrección propuesta

`.env.example` solo con lo que el usuario debe o puede elegir en Docker (puertos, orígenes, llave de DeepSeek, límites), agrupado y comentado; los valores internos de Docker quedan en el compose. Los del modo sin Docker, en un bloque comentado o en el README. No escribir secretos en archivos versionados. Proponer (no aplicar) los cambios a `.env` local: el agente no lo edita sin dejarlo indicado en el informe.

## Notas

`.env` contiene la llave real: no se lee en voz alta, no se copia a docs ni a commits.

Decisiones (opción recomendada):

- `.env.example` agrupado por lo que el usuario elige en Docker (puertos/usuario, DeepSeek, límites, login, S3) con
  una cabecera que dice qué fija el compose (`DATABASE_URL`, `DATA_DIR`, `S3_ENDPOINT`, `CORS_ORIGINS`). Esos cuatro
  quedan comentados en un bloque final «Solo sin Docker» (Docker los ignora; sin Docker `S3_ENDPOINT` es el único
  sin valor por defecto útil: vacío = AWS). `docker-compose.yml` no cambia.
- `S3_CORS_ORIGINS` pasa a comentado: sin definir, el compose ya añade `http://localhost:WEB_PORT` a `:3000` y
  `:5173` (definido en `.env` pierde el origen de `WEB_PORT`). `S3_INTERNAL_ENDPOINT`/`S3_PUBLIC_ENDPOINT`,
  documentados y comentados (solo para otro proveedor).
- README: la tabla de Configuración gana la columna «Modo» (Docker / ambos / sin Docker) y todas las variables de
  `.env.example`; «Desarrollo local (sin Docker)» remite al bloque «Solo sin Docker».

Cambios propuestos para el `.env` local (no aplicados; el agente no lo edita). Leídos solo los nombres:

- Borrar o comentar `DATABASE_URL`, `DATA_DIR`, `S3_ENDPOINT` y `CORS_ORIGINS` (los sobrescribe el compose); si se
  usa también el modo sin Docker, moverlos a un bloque comentado «Solo sin Docker» como en `.env.example`.
- Valorar quitar `S3_CORS_ORIGINS` para que el compose incluya `http://localhost:WEB_PORT` automáticamente (revisar
  antes que su valor actual no añada orígenes propios).
- Cabecera «Método de traducción» → «API de DeepSeek» (resto de la suscripción, #07).
- Borrar esos cuatro no cambia los valores efectivos en Docker (`docker compose config` ya usa los del compose); quitar `S3_CORS_ORIGINS` sí cambia el CORS del bucket (tras `docker compose run --rm storage-init`).
