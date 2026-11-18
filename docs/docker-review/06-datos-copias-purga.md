# 06 · Sin copias de seguridad de SQLite ni purga programada

- **Severidad:** Alto
- **Categoría:** Datos
- **Estado:** abierto
- **Ubicación:** `docker-compose.yml` (`./data:/data` bind mount), `README.md` (paso `mkdir data`, purga «prográmala si quieres»), `backend/app/cli.py` (`purge`)
- **Aceptación:** [06-datos-copias-purga.aceptacion.md](06-datos-copias-purga.aceptacion.md)

## Problema

La BD (`data/app.db`, WAL) y los PDFs viven en un bind mount que hay que crear a mano con el UID correcto. No existe
ninguna copia automática: las únicas copias son las que hicieron a mano las fichas de migración
(`data/app.db.bak-review09/10`). La purga de sesiones y bitácora (#16 del backend) depende de un cron en el host.

## Cómo reproducirlo

`ls data/` muestra solo copias manuales; no hay servicio ni comando de copia; la purga no corre sola.

## Impacto

Una migración fallida, un disco lleno o un borrado accidental pierden todos los libros y correcciones sin forma de recuperarlos.

## Corrección propuesta

Servicio(s) en el compose que reutilicen la imagen del backend: copia diaria consistente con WAL (API de backup de sqlite3 o `VACUUM INTO`) a `data/backups/` con retención (p. ej. 7 diarias), y la purga diaria (`app.cli purge`). Comando para copia y **restauración** documentados (restaurar exige parar api y worker). Mantener el bind mount `./data` (los PDFs deben seguir accesibles en el host); documentar el `mkdir data` o crearlo con el UID correcto de forma segura.

## Notas

Probar la restauración SOLO sobre una copia (p. ej. levantar un stack temporal con otra carpeta de datos o restaurar a un archivo aparte y comprobarlo), nunca sobrescribiendo `data/app.db`. Si hay que reiniciar api/worker, comprobar antes que no hay trabajos activos.
