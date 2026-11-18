# 05 · `.env` y `.env.example` mezclan valores del modo host con los de Docker

- **Severidad:** Bajo
- **Categoría:** Configuración
- **Estado:** abierto
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
