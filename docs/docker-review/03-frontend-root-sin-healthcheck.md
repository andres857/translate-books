# 03 · El contenedor del frontend corre como root y sin healthcheck

- **Severidad:** Medio
- **Categoría:** Seguridad / robustez
- **Estado:** resuelto · commit(s) `fb52dad`
- **Ubicación:** `frontend/Dockerfile` (stage final), `docker-compose.yml` (`frontend`)
- **Aceptación:** [03-frontend-root-sin-healthcheck.aceptacion.md](03-frontend-root-sin-healthcheck.aceptacion.md)

## Problema

La imagen final de `node:22-alpine` no declara `USER`, así que `node server.js` corre como root; no hay `HEALTHCHECK`
ni `healthcheck` en el compose, de modo que `docker compose ps` no distingue un Next colgado de uno sano.

## Cómo reproducirlo

`docker compose exec frontend id` → `uid=0(root)`; `docker compose ps frontend` sin `(healthy)`.

## Impacto

Una vulnerabilidad en Next o en una dependencia obtiene root dentro del contenedor; un fallo silencioso no se detecta.

## Corrección propuesta

`USER node` (el usuario que trae la imagen) con los archivos copiados con `--chown=node:node`; healthcheck con `wget -qO- http://127.0.0.1:3000/login` (alpine trae `wget`) o un script node equivalente.

## Notas

- Decisión: `HEALTHCHECK` en el `Dockerfile` (como el backend) en vez de en el compose, con `wget -qO /dev/null http://127.0.0.1:3000/login` (interval 15s, timeout 5s, start-period 20s, retries 3); sin dependencias nuevas.
- `.next` queda propiedad de `node`, así que Next puede crear `.next/cache` en ejecución. Imagen: 336 MB (igual que antes).
